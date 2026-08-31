"""Shared plumbing for the browser end-to-end tests.

Every selenium module in this package builds on :class:`SeleniumTestCase`,
which owns the driver lifecycle, the skip conditions and the login helper, so
a test module only describes what it drives.

The selenium imports live at module level inside a ``try``: that keeps them out
of the functions (``make lint`` rejects function-level imports, PLC0415) while
still letting the package import cleanly when selenium is not installed --
``HAS_SELENIUM`` is then False and every case skips itself.

Requirements: selenium, a chromium + chromedriver. Tagged ``selenium``, so the
default suite (``--exclude-tag=selenium``) never starts a browser::

    make test-selenium              # everything tagged selenium, inside Xvfb
    make test-selenium-run          # the same, on the caller's own display
    python manage.py test demoapp.tests.selenium.test_widgets --tag=selenium

``make test-selenium`` wraps the run in ``xvfb-run -a``, so the browser lives on
a display of its own and never steals focus from the session that launched it.
"""

import contextlib
import os
import shutil
import tempfile
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test.testcases import LiveServerThread, QuietWSGIRequestHandler

try:
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    HAS_SELENIUM = True
except ImportError:                                  # pragma: no cover
    HAS_SELENIUM = False
    By = EC = Keys = WebDriverWait = None
    WebDriverException = Exception


class NonKeepAliveHandler(QuietWSGIRequestHandler):
    """Answer HTTP/1.0, so every request gets a connection of its own.

    Django's live server keeps HTTP/1.1 connections alive and dedicates a
    thread to each. A page that opens ten XHRs at once -- /chartjs does, one
    per chart -- exhausts that pool, and the requests that do not fit simply
    never get served: the test then waits out its timeout on a widget that
    would have worked in a real browser. Closing each connection costs a few
    milliseconds per request and makes the suite deterministic.
    """

    protocol_version = 'HTTP/1.0'


class NonKeepAliveLiveServerThread(LiveServerThread):
    def _create_server(self, connections_override=None):
        return self.server_class(
            (self.host, self.port), NonKeepAliveHandler,
            allow_reuse_address=False,
            connections_override=connections_override)


CHROMEDRIVER = os.getenv('CHROMEDRIVER', '/usr/bin/chromedriver')
CHROMIUM = os.getenv('CHROME_BIN', '/usr/bin/chromium')

# Headless is the default: it is what CI wants and what a bare `manage.py test
# --tag=selenium` should do on a machine with no X server at all.
# SELENIUM_HEADLESS=0 draws a real browser instead, which is only worth it
# inside the Xvfb that `make test-selenium` starts -- Leaflet, the canvases and
# TinyMCE then render the way they do for a user, without a window ever
# appearing on the developer's own display.
HEADLESS = os.getenv('SELENIUM_HEADLESS', '1').lower() not in ('0', 'false', 'no')

USERNAME = 'admin'
PASSWORD = 'admin12345'

# The size every test starts at, and the one `viewport()` restores. It has to
# match the --window-size flag below, or the first test to resize would leave
# every later test running at a size nobody chose.
DEFAULT_VIEWPORT = (1500, 1100)

# Generous: a cold page pulls the whole bundled vendor javascript before any
# widget initialises, and CI machines are slower than a developer laptop.
TIMEOUT = 25


class SeleniumTestCase(StaticLiveServerTestCase):
    """Live server + chromium (headless unless ``SELENIUM_HEADLESS=0``), with a
    superuser already logged in.

    Subclasses get ``self.driver``, ``self.wait``, and the ``go``/``js``/
    ``wait_js`` helpers. Override :meth:`setup_data` to create fixtures; it
    runs before the login so the first page already has something to show.
    """

    server_thread_class = NonKeepAliveLiveServerThread

    @classmethod
    def setUpClass(cls):
        if not HAS_SELENIUM:
            raise unittest.SkipTest('selenium not installed')
        if not os.path.exists(CHROMEDRIVER):
            raise unittest.SkipTest(f'chromedriver not at {CHROMEDRIVER}')

        super().setUpClass()
        opts = Options()
        if HEADLESS:
            opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=%d,%d' % DEFAULT_VIEWPORT)
        # A silent fake microphone, auto-granted: the voice widgets ask for
        # getUserMedia, and without these the browser either blocks on a
        # permission prompt no test can answer or fails outright.
        opts.add_argument('--use-fake-ui-for-media-stream')
        opts.add_argument('--use-fake-device-for-media-stream')
        # Silences the noisy "DevTools listening" / GPU lines that otherwise
        # bury the test output.
        opts.add_argument('--log-level=3')
        opts.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        if os.path.exists(CHROMIUM):
            opts.binary_location = CHROMIUM
        cls.driver = webdriver.Chrome(
            service=Service(CHROMEDRIVER), options=opts)
        # Small implicit wait as a floor; the explicit waits below do the real
        # synchronising. Keep it low or every negative assertion pays it.
        cls.driver.implicitly_wait(1)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'driver', None):
            cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username=USERNAME, email='admin@example.com', password=PASSWORD)
        self.user.is_superuser = self.user.is_staff = True
        self.user.save()
        self.wait = WebDriverWait(self.driver, TIMEOUT)
        self.setup_data()
        self.login()

    # -- hooks ---------------------------------------------------------------
    def setup_data(self):
        """Create whatever the page under test needs. Overridden downstream."""

    # -- fixtures ------------------------------------------------------------
    def write_temp_file(self, name, content):
        """A real file on disk, for send_keys() into an <input type=file>.

        WebDriver uploads by path, so the browser needs something it can open;
        the directory goes away with the test.
        """
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        path = os.path.join(directory, name)
        with open(path, 'wb') as handle:
            handle.write(content)
        return path

    # -- navigation ----------------------------------------------------------
    def login(self):
        d = self.driver
        d.get(f'{self.live_server_url}/accounts/login/')
        self.wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        d.find_element(By.NAME, 'username').send_keys(USERNAME)
        d.find_element(By.NAME, 'password').send_keys(PASSWORD)
        d.find_element(
            By.CSS_SELECTOR, 'button[type=submit],input[type=submit]').click()
        self.wait.until_not(
            EC.presence_of_element_located((By.NAME, 'password')))

    def go(self, path):
        """Open ``path`` and block until jQuery has finished booting the page.

        Every widget in this project is a jQuery plugin wired on ready, so
        "document complete" is not enough: without this the first assertion
        races the widget initialisation.
        """
        self.driver.get(f'{self.live_server_url}{path}')
        self.wait_js(
            "return document.readyState === 'complete' "
            "&& typeof jQuery !== 'undefined' && jQuery.isReady")

    # -- viewport ------------------------------------------------------------
    def set_viewport(self, width, height):
        """Resize the *layout* viewport to exactly ``width`` x ``height``.

        ``set_window_size`` sizes the OUTER window, which is the wrong number
        twice over: it includes the browser chrome, so the page gets a viewport
        tens of pixels shorter than asked, and Chrome on Linux refuses to go
        below roughly 500x160 -- which would silently invalidate exactly the
        narrow cases these tests exist for. The CDP override sets the layout
        viewport itself, so the media query under test is the one that fires,
        it behaves the same headless or headed, and it has no floor.

        Nothing in this suite restored the window size before, so the cleanup
        matters: without it the first test to resize poisons every test after.
        """
        try:
            self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height,
                'deviceScaleFactor': 1, 'mobile': False})
            self.addCleanup(self._clear_viewport)
        except (AttributeError, WebDriverException):   # pragma: no cover
            # Not a Chromium driver. Aim the outer window, then correct for the
            # chrome by however much the inner size came up short.
            self.addCleanup(self.driver.set_window_size, *DEFAULT_VIEWPORT)
            outer_w, outer_h = width, height
            for _ in range(3):
                self.driver.set_window_size(outer_w, outer_h)
                inner_w = self.js('return window.innerWidth')
                inner_h = self.js('return window.innerHeight')
                if (inner_w, inner_h) == (width, height):
                    break
                outer_w += width - inner_w
                outer_h += height - inner_h

        self.wait_js(
            'return window.innerWidth === arguments[0]'
            ' && window.innerHeight === arguments[1];',
            width, height,
            message=f'the viewport never became {width}x{height}')
        self.settle()

    def _clear_viewport(self):
        with contextlib.suppress(WebDriverException):
            self.driver.execute_cdp_cmd(
                'Emulation.clearDeviceMetricsOverride', {})

    @contextlib.contextmanager
    def viewport(self, width, height):
        """Run a block at a given viewport, then restore the default one."""
        self.set_viewport(width, height)
        try:
            yield
        finally:
            self._clear_viewport()
            self.set_viewport(*DEFAULT_VIEWPORT)

    def settle(self):
        """Wait out the layout that a resize or a toggle kicks off.

        custom.js debounces its own resize handling by 100ms (``smartresize``),
        and the drawer transitions for 200ms. Rather than sleep for a guessed
        total, wait until the sidebar's box has stopped moving between two
        polls -- that is the thing the assertions read.

        The reset matters: without it the first poll compares against whatever
        the *previous* settle left behind, which for a drawer that has only
        just started sliding is still its closed position. The wait then
        returns mid-transition and every measurement after it is of a menu
        caught halfway across the screen.
        """
        self._last_boxes = None
        self.wait.until(
            lambda d: self._box_settled(),
            'the layout never stopped moving')

    def _box_settled(self):
        boxes = self.js(
            "const r = s => { const e = document.querySelector(s);"
            "  if (!e) return 'none';"
            "  const b = e.getBoundingClientRect();"
            "  return [b.top, b.left, b.width, b.height].join(','); };"
            "return [r('.col-md-3.left_col'), r('.sidebar-footer'),"
            "        r('#sidebar-menu')].join('|');")
        settled = boxes == getattr(self, '_last_boxes', None)
        self._last_boxes = boxes
        return settled

    # -- element state -------------------------------------------------------
    STATE_JS = (
        "const e = typeof arguments[0] === 'string'"
        "        ? document.querySelector(arguments[0]) : arguments[0];"
        "if (!e) return null;"
        "const r = e.getBoundingClientRect();"
        "const cs = getComputedStyle(e);"
        "const cx = r.left + r.width / 2, cy = r.top + r.height / 2;"
        "const onScreen = cx >= 0 && cy >= 0"
        "              && cx <= window.innerWidth && cy <= window.innerHeight;"
        "const hit = (r.width > 0 && r.height > 0 && onScreen)"
        "          ? document.elementFromPoint(cx, cy) : null;"
        "return {"
        "  width: r.width, height: r.height, top: r.top, left: r.left,"
        "  right: r.right, bottom: r.bottom,"
        "  display: cs.display, visibility: cs.visibility, opacity: cs.opacity,"
        "  inViewport: r.top >= -0.5 && r.left >= -0.5"
        "           && r.right <= window.innerWidth + 0.5"
        "           && r.bottom <= window.innerHeight + 0.5,"
        "  topmost: !!hit && (hit === e || e.contains(hit)),"
        "  text: (e.textContent || '').replace(/\\s+/g, ' ').trim()"
        "};")

    def element_state(self, target):
        """Geometry + visibility + hit-testing for one element, in one hop.

        ``target`` is a CSS selector or a WebElement. Returns None when there
        is no such element.

        ``topmost`` accepts the element itself or a descendant -- an anchor hit
        on its own <i> is a real hit -- but deliberately NOT an ancestor: an
        overlay drawn over the anchor has to fail, and that asymmetry is what
        catches a fixed footer bar painted across a menu row.
        """
        return self.js(self.STATE_JS, target)

    def scroll_into_view(self, target):
        """Bring ``target`` into its scroll container, the way a user would.

        A menu taller than its box is not broken -- it scrolls. So an entry
        below the fold has to be *reachable*, not already on screen, and these
        assertions are about reach.
        """
        self.js(
            "const e = typeof arguments[0] === 'string'"
            "        ? document.querySelector(arguments[0]) : arguments[0];"
            "if (e) e.scrollIntoView({block: 'nearest', inline: 'nearest'});",
            target)

    def assert_reachable(self, target, message=''):
        """Assert a user could get to ``target`` and click it."""
        self.scroll_into_view(target)
        return self.assert_clickable(target, message=message)

    def assert_clickable(self, target, message=''):
        """Assert a user could actually click ``target`` right now."""
        state = self.element_state(target)
        prefix = f'{message}: ' if message else ''
        self.assertIsNotNone(state, f'{prefix}{target} is not in the page')
        self.assertTrue(
            state['width'] > 0 and state['height'] > 0,
            f'{prefix}{target} has no size ({state["width"]}x{state["height"]})')
        self.assertNotEqual(
            state['display'], 'none', f'{prefix}{target} is display:none')
        self.assertEqual(
            state['visibility'], 'visible',
            f'{prefix}{target} is visibility:{state["visibility"]}')
        # A transparent control still answers elementFromPoint, so without this
        # a checkbox left at `opacity: 0` for a widget library that no longer
        # exists passes every other check while being invisible on screen.
        self.assertGreater(
            float(state['opacity']), 0,
            f'{prefix}{target} is fully transparent')
        self.assertTrue(
            state['inViewport'],
            f'{prefix}{target} is outside the viewport '
            f'(top={state["top"]:.0f} left={state["left"]:.0f} '
            f'right={state["right"]:.0f} bottom={state["bottom"]:.0f}, '
            f'viewport {self.js("return window.innerWidth")}x'
            f'{self.js("return window.innerHeight")})')
        self.assertTrue(
            state['topmost'],
            f'{prefix}{target} is covered by something else')
        return state

    def assert_no_horizontal_scroll(self, message=''):
        """The page must never scroll sideways at any width."""
        width = self.js('return document.documentElement.scrollWidth')
        inner = self.js('return window.innerWidth')
        self.assertLessEqual(
            width, inner + 1,
            f'{message}the document scrolls horizontally '
            f'({width}px of content in a {inner}px viewport)')

    # -- javascript ----------------------------------------------------------
    def js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def wait_js(self, script, *args, message=''):
        """Wait until ``script`` returns something truthy."""
        return self.wait.until(
            lambda d: d.execute_script(script, *args),
            message or f'javascript never became true: {script[:80]}')

    # -- assertions ----------------------------------------------------------
    def assert_widget_ready(self, css, message=''):
        """Assert the element exists and its jQuery plugin has initialised.

        Uses the ``data-widget`` attribute the library stamps on every widget
        it renders, which is the stable contract; class names come from the
        third party plugins and move between versions.
        """
        found = self.js(
            "const e = document.querySelector(arguments[0]);"
            "return e ? (e.dataset.widget || 'present') : null;", css)
        self.assertIsNotNone(
            found, message or f'{css} is not in the page')
        return found

    def rows_of(self, table_css):
        """Visible data rows of a DataTable, as a list of row texts."""
        return self.js(
            "return Array.from(document.querySelectorAll("
            "  arguments[0] + ' tbody tr'))"
            "  .filter(tr => !tr.querySelector('td.dt-empty'))"
            "  .map(tr => tr.textContent.replace(/\\s+/g,' ').trim());",
            table_css)

    def wait_rows(self, table_css, predicate, message=''):
        """Wait until ``predicate(rows)`` holds for the table's rows."""
        return self.wait.until(
            lambda d: predicate(self.rows_of(table_css)) and True,
            message or f'{table_css} never reached the expected state')
