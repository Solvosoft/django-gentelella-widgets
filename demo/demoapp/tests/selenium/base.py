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

import os
import unittest

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    HAS_SELENIUM = True
except ImportError:                                  # pragma: no cover
    HAS_SELENIUM = False
    By = EC = WebDriverWait = None

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
        opts.add_argument('--window-size=1500,1100')
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
            "  .filter(tr => !tr.querySelector('td.dataTables_empty'))"
            "  .map(tr => tr.textContent.replace(/\\s+/g,' ').trim());",
            table_css)

    def wait_rows(self, table_css, predicate, message=''):
        """Wait until ``predicate(rows)`` holds for the table's rows."""
        return self.wait.until(
            lambda d: predicate(self.rows_of(table_css)) and True,
            message or f'{table_css} never reached the expected state')
