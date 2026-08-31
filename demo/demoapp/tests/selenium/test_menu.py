"""The menus at every viewport size: nothing may be lost, hidden or unclickable.

The bug this module reproduces, from a 546x247 window:

  * only two of the three sidebar-footer icons were on screen. ``.sidebar-footer``
    is ``position: fixed``, so the ``.nohidden { width: 200% }`` rule resolved
    against the VIEWPORT: the bar became twice the window wide and each anchor,
    at ``width: 25%``, took half the screen. The third icon -- the help palette
    -- sat past the right edge, reachable by nobody.
  * the menu was cut off mid-entry with no way to scroll to the rest, because
    the column was ``overflow-hidden`` and the fixed footer bar was painted
    over whatever entries reached the bottom.
  * below 992px the sidebar was ``display: none`` outright, and the only escape
    was a 70px icon rail whose second- and third-level flyouts were 70px wide
    at a hardcoded ``top: 80px``.

So every assertion here is about a user's reach, not about a class name: is the
thing on screen, is it the topmost element at its own centre, can it be scrolled
to. The sizes are swept with ``subTest`` so one run names every broken width
rather than stopping at the first.
"""

from django.test import tag
from django.urls import reverse

from djgentelella.models import Help, MenuItem
from .base import SeleniumTestCase

PAGE = '/knobwidget/testform'

# (label, width, height). The last two are the screenshot: a window shorter
# than the menu, and the 546x247 one where the palette fell off the edge.
SIZES = (
    ('desktop', 1500, 1100),
    ('laptop', 1200, 800),
    ('boundary-992', 992, 800),
    ('boundary-991', 991, 800),
    ('tablet', 768, 1024),
    ('phone', 400, 800),
    ('short', 900, 400),
    ('tiny', 560, 260),
)

# Enough level-1 entries that the menu is taller than any window here; without
# that the scrolling assertions would pass on a menu that simply fits.
FILLER = (
    'Datatables', 'Object Management', 'Form Widgets', 'ReadOnly Widgets',
    'Maps', 'Blog', 'Trash', 'History', 'Notifications', 'Permissions',
    'Autocomplete', 'Charts',
)


class MenuTestBase(SeleniumTestCase):
    """A sidebar three levels deep, plus a four-icon footer ending in the palette."""

    def setup_data(self):
        # -- sidebar: section > level 1 > level 2 > level 3 -------------------
        home = MenuItem.objects.create(
            parent=None, title='Home', url_name='/', category='sidebar',
            is_reversed=False, is_widget=False, icon='fa fa-home', position=0)
        self.dashboard = MenuItem.objects.create(
            parent=home, title='Dashboard', url_name='/', category='sidebar',
            is_reversed=False, is_widget=False, icon='fa fa-tachometer',
            position=0)
        # The entry the screenshot cut in half.
        MenuItem.objects.create(
            parent=home, title='Crud / notifications', url_name='/',
            category='sidebar', is_reversed=False, is_widget=False,
            icon='fa fa-plus-circle', position=1)

        widgets = MenuItem.objects.create(
            parent=None, title='Custom Widgets', url_name='/',
            category='sidebar', is_reversed=False, is_widget=False,
            icon='fa fa-cubes', position=1)
        self.level1 = MenuItem.objects.create(
            parent=widgets, title='Formset Widgets', url_name='/',
            category='sidebar', is_reversed=False, is_widget=False,
            icon='fa fa-list', position=0)
        self.level2 = MenuItem.objects.create(
            parent=self.level1, title='Formset add', url_name='/',
            category='sidebar', is_reversed=False, is_widget=False,
            icon='fa fa-plus', position=0)
        self.level3 = [
            MenuItem.objects.create(
                parent=self.level2, title=title, url_name='/',
                category='sidebar', is_reversed=False, is_widget=False,
                icon='fa fa-file-o', position=i)
            for i, title in enumerate(('Model Formset', 'Inline Formset'))
        ]
        for i, title in enumerate(FILLER):
            MenuItem.objects.create(
                parent=widgets, title=title, url_name='/', category='sidebar',
                is_reversed=False, is_widget=False, icon='fa fa-square-o',
                position=i + 1)

        # -- sidebar footer: three plain icons, then the palette --------------
        for i, icon in enumerate(
                ('fa fa-power-off', 'fa fa-cog', 'fa fa-user')):
            MenuItem.objects.create(
                parent=None, title='', url_name='/', category='sidebarfooter',
                is_reversed=False, is_widget=False, icon=icon,
                only_icon=True, position=i)
        # Last, so it is the one that falls off the right edge -- which is the
        # reported symptom, "la ayuda de la paleta se pierde".
        self.palette = MenuItem.objects.create(
            parent=None, title='', category='sidebarfooter',
            url_name='djgentelella.menu_widgets.palette.PalleteWidget',
            is_reversed=False, reversed_kwargs=None,
            reversed_args=reverse('help'), is_widget=True,
            icon='fa fa-question-circle', only_icon=True, position=3)
        Help.objects.create(
            id_view='knobwidgets', question_name='id_age',
            help_title='Sobre la edad', help_text='La edad en años cumplidos.')

        # -- top menu: two levels of Bootstrap dropdown -----------------------
        top = MenuItem.objects.create(
            parent=None, title='Base 2', url_name='/', category='main',
            is_reversed=False, is_widget=False, icon='fa fa-cog', position=0)
        self.top_level1 = MenuItem.objects.create(
            parent=top, title='Base 2 de 2', url_name='/', category='main',
            is_reversed=False, is_widget=False, icon='', position=0)
        self.top_level2 = [
            MenuItem.objects.create(
                parent=self.top_level1, title=title, url_name='/',
                category='main', is_reversed=False, is_widget=False,
                icon='', position=i)
            for i, title in enumerate(('Base 2 de 2 de 1', 'Base 2 de 2 de 2'))
        ]
        # A third nested level, the depth `demomenu` builds and the one the
        # narrow bar had no room for.
        self.top_level3 = [
            MenuItem.objects.create(
                parent=self.top_level2[0], title=title, url_name='/',
                category='main', is_reversed=False, is_widget=False,
                icon='', position=i)
            for i, title in enumerate(
                ('Base 2 de 2 de 1 de 1', 'Base 2 de 2 de 1 de 2'))
        ]
        # A fourth, matching the depth `demomenu` ships: the top menu draws its
        # own submenus, so each extra level is a level that can break on its
        # own.
        self.top_level4 = [
            MenuItem.objects.create(
                parent=self.top_level3[0], title=title, url_name='/',
                category='main', is_reversed=False, is_widget=False,
                icon='', position=i)
            for i, title in enumerate(
                ('Base 2 de 2 de 1 de 1 de 1', 'Base 2 de 2 de 1 de 1 de 2'))
        ]
        self.top = top

    # -- page ----------------------------------------------------------------
    def open_page(self):
        self.go(PAGE)
        self.wait_js(
            "return document.querySelectorAll('#sidebar-menu a').length > 0;",
            message='the sidebar menu never rendered')

    # -- state ---------------------------------------------------------------
    def rendered(self, css):
        """Selectors of the elements matching ``css`` that are laid out.

        "Laid out" means the box exists -- so an entry pushed off the edge of
        the window still counts, which is the whole point: that is the failure
        being hunted, not an absence.
        """
        return self.js(
            "return Array.from(document.querySelectorAll(arguments[0]))"
            "  .filter(e => e.getClientRects().length > 0 && e.id)"
            "  .map(e => '#' + CSS.escape(e.id));", css)

    def sidebar_is_reachable(self):
        state = self.element_state('.col-md-3.left_col')
        return bool(state) and state['display'] != 'none' \
            and state['visibility'] == 'visible' and state['right'] > 0

    def toggle_menu(self):
        """Press the hamburger and wait for the layout to finish reacting."""
        self.js("document.querySelector('#menu_toggle').click();")
        self.settle()

    def ensure_menu_visible(self):
        """Whatever it takes at this width, get the menu on screen.

        Deliberately phrased as an outcome rather than "add class X": the point
        of the test is that a user can reach the menu, not how.
        """
        if not self.sidebar_is_reachable():
            self.toggle_menu()
        return self.sidebar_is_reachable()

    def submenu_is_open(self, item):
        return self.js(
            "const a = document.querySelector(arguments[0]);"
            "const ul = a && a.closest('li').querySelector(':scope > ul');"
            "return !!ul && getComputedStyle(ul).display !== 'none'"
            "       && ul.getBoundingClientRect().height > 0;",
            '#sb%d' % item.pk)

    def open_branch(self, item):
        """Click a parent entry and wait for its own submenu to unfold.

        Idempotent on purpose: the entry is a toggle, so clicking one that is
        already open would fold it shut again -- which is what happened when
        the same branch was walked once per viewport size in a loop.
        """
        if self.submenu_is_open(item):
            return
        self.js('document.querySelector(arguments[0]).click();',
                '#sb%d' % item.pk)
        self.wait_js(
            "const li = document.querySelector(arguments[0]).closest('li');"
            "const ul = li && li.querySelector(':scope > ul');"
            "return !!ul && getComputedStyle(ul).display !== 'none'"
            "       && ul.getBoundingClientRect().height > 0;",
            '#sb%d' % item.pk,
            message='the submenu of %r never opened' % item.title)
        self.settle()


@tag('selenium')
class SidebarReachTest(MenuTestBase):
    """Every entry the sidebar draws has to be on screen and hittable."""

    def test_every_rendered_sidebar_entry_is_clickable(self):
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(
                    self.ensure_menu_visible(),
                    f'[{label}] the sidebar cannot be brought on screen at '
                    f'{width}x{height}')
                anchors = self.rendered('#sidebar-menu a')
                self.assertGreaterEqual(
                    len(anchors), 3,
                    f'[{label}] the sidebar draws almost nothing at '
                    f'{width}x{height}: {anchors}')
                for css in anchors:
                    self.assert_reachable(css, message=f'[{label}]')

    def test_every_footer_icon_is_clickable(self):
        """The reported bug: the palette is the last icon and it fell off."""
        self.open_page()
        expected = MenuItem.objects.filter(category='sidebarfooter').count()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(self.ensure_menu_visible(), label)
                icons = self.rendered('.sidebar-footer > a')
                self.assertEqual(
                    len(icons), expected,
                    f'[{label}] the footer draws {len(icons)} of {expected} '
                    f'icons at {width}x{height}')
                for css in icons:
                    self.assert_clickable(css, message=f'[{label}]')

    def test_the_footer_bar_is_never_wider_than_its_own_column(self):
        """`width: 200%` on a fixed box means 200% of the WINDOW, not the column."""
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(self.ensure_menu_visible(), label)
                column = self.element_state('.col-md-3.left_col')
                footer = self.element_state('.sidebar-footer')
                overhang = footer['right'] - column['right']
                self.assertLessEqual(
                    footer['right'], column['right'] + 1,
                    f'[{label}] the footer bar sticks {overhang:.0f}px out '
                    f'of the sidebar')

    def test_the_footer_never_covers_the_menu(self):
        """It was `position: fixed; bottom: 0`, painted over the last entries.

        Asserted against the scrolling menu box rather than each entry: an
        entry below the fold is clipped by that box, so its rectangle overlaps
        the footer's without a single pixel of it being hidden. What has to
        hold is structural -- the strip is a sibling below the scroller, in
        flow, not a fixed bar floating on top of it.
        """
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(self.ensure_menu_visible(), label)
                menu = self.element_state('#sidebar-menu')
                footer = self.element_state('.sidebar-footer')
                self.assertGreaterEqual(
                    footer['top'], menu['bottom'] - 1,
                    f'[{label}] the footer bar overlaps the last '
                    f'{menu["bottom"] - footer["top"]:.0f}px of the menu')
                self.assertLessEqual(
                    footer['bottom'], height + 1,
                    f'[{label}] the footer bar hangs below the window')

    def test_the_document_never_scrolls_horizontally(self):
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assert_no_horizontal_scroll(message=f'[{label}] ')
                self.ensure_menu_visible()
                self.assert_no_horizontal_scroll(message=f'[{label}] open: ')


@tag('selenium')
class SidebarLevelsTest(MenuTestBase):
    """Levels 2 and 3 have to be reachable, collapsed rail included."""

    def assert_children_reachable(self, label):
        self.open_branch(self.level1)
        self.assert_reachable('#sb%d' % self.level2.pk, message=f'[{label}] L2')
        self.open_branch(self.level2)
        for child in self.level3:
            self.assert_reachable('#sb%d' % child.pk, message=f'[{label}] L3')

    def test_the_second_and_third_level_open_and_are_clickable(self):
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(self.ensure_menu_visible(), label)
                self.assert_children_reachable(label)

    def test_the_levels_are_reachable_in_the_collapsed_rail(self):
        """`.nav-sm ul.nav.child_menu` was 70px wide at a hardcoded top: 80px.

        A hardcoded ``top`` means the flyout opens where the menu happens to
        start rather than beside the entry it belongs to -- so it lands on top
        of the rail and hides the very entries the user was navigating. Being
        merely on screen is not enough here: it has to sit *beside* the rail,
        be wide enough to read, and leave its own parent reachable.
        """
        self.open_page()
        self.set_viewport(1500, 1100)
        self.toggle_menu()
        self.wait_js("return document.body.classList.contains('nav-sm');",
                     message='the hamburger never collapsed the sidebar')
        self.assert_children_reachable('rail')

        rail = self.element_state('.col-md-3.left_col')
        flyout = self.element_state('#sb%d + ul' % self.level1.pk)
        self.assertGreaterEqual(
            flyout['left'], rail['right'] - 1,
            'the rail flyout is drawn on top of the rail instead of beside '
            'it, hiding the entries behind it')
        self.assertGreater(
            flyout['width'], 150,
            f'the rail flyout is {flyout["width"]:.0f}px wide -- too narrow '
            f'to read a submenu label in')
        self.assert_clickable(
            '#sb%d' % self.level1.pk,
            message='its own parent, after opening the flyout')


@tag('selenium')
class SidebarScrollTest(MenuTestBase):
    """A menu taller than the window has to be scrollable to its end."""

    def test_the_last_entry_can_be_scrolled_to(self):
        self.open_page()
        for label, width, height in (('short', 900, 400), ('phone', 400, 800)):
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.assertTrue(self.ensure_menu_visible(), label)
                # The scroll position survives a resize, and the previous case
                # left it at the bottom.
                self.js("document.querySelector('#sidebar-menu').scrollTop = 0;")
                self.settle()

                scroller = self.js(
                    "const e = document.querySelector('#sidebar-menu');"
                    "return [e.scrollHeight, e.clientHeight,"
                    "        getComputedStyle(e).overflowY];")
                self.assertGreater(
                    scroller[0], scroller[1],
                    f'[{label}] the menu is not taller than its box, so this '
                    f'test proves nothing -- add more entries')
                self.assertIn(
                    scroller[2], ('auto', 'scroll'),
                    f'[{label}] the menu overflows its box but cannot be '
                    f'scrolled (overflow-y: {scroller[2]})')

                last = self.rendered('#sidebar-menu a')[-1]
                before = self.element_state(last)
                self.assertFalse(
                    before['inViewport'],
                    f'[{label}] the last entry is already on screen, so '
                    f'scrolling is not what is being tested')

                self.js("document.querySelector('#sidebar-menu')"
                        ".scrollTop = 1e6;")
                self.settle()
                self.assert_clickable(last, message=f'[{label}] after scrolling')


@tag('selenium')
class SidebarDrawerTest(MenuTestBase):
    """Below 992px the menu is a drawer -- it must open, close and keep its text."""

    def test_the_drawer_keeps_the_labels_readable(self):
        """The whole point of a drawer over a 70px rail.

        The rail does technically still contain the words, shrunk to 10px and
        wrapped inside 70px, which is how the menu "kept its content" while
        being unusable. So this measures the room a label actually gets.
        """
        self.open_page()
        self.set_viewport(400, 800)
        self.assertTrue(self.ensure_menu_visible())

        label = self.element_state('#sb%d' % self.dashboard.pk)
        self.assertIsNotNone(label, 'the Dashboard entry is not in the page')
        self.assertEqual(
            label['text'], 'Dashboard',
            'the narrow menu lost its labels')
        self.assertGreater(
            label['width'], 150,
            f'the entry gets {label["width"]:.0f}px of width on a 400px '
            f'window: that is the icon rail, not the menu')
        font = self.js(
            'return parseFloat(getComputedStyle('
            '  document.querySelector(arguments[0])).fontSize);',
            '#sb%d' % self.dashboard.pk)
        self.assertGreaterEqual(
            font, 12,
            f'the label is rendered at {font}px, too small to read')

    def test_the_backdrop_closes_the_drawer(self):
        self.open_page()
        self.set_viewport(400, 800)
        self.assertTrue(self.ensure_menu_visible())
        first = self.rendered('#sidebar-menu a')[0]
        self.assert_clickable(first, message='drawer open')

        self.js("document.querySelector('.sidebar-backdrop').click();")
        self.settle()
        self.assertFalse(
            self.sidebar_is_reachable(),
            'the drawer stayed open after the backdrop was clicked')


@tag('selenium')
class PalettePanelTest(MenuTestBase):
    """The help panel has to fit the window it is opened in."""

    def open_panel(self):
        self.js("document.querySelector('#fsb_%d').click();" % self.palette.pk)
        self.wait_js(
            "const p = document.querySelector('[id^=content_tm_]');"
            "return p && p.classList.contains('show');",
            message='the help panel never opened')
        self.settle()

    def test_the_panel_opens_inside_the_viewport_at_every_size(self):
        self.open_page()
        self.assertTrue(self.ensure_menu_visible())
        self.open_panel()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                state = self.element_state('[id^=content_tm_]')
                self.assertTrue(
                    state['inViewport'],
                    f'[{label}] the help panel hangs outside a {width}x{height} '
                    f'window (top={state["top"]:.0f} left={state["left"]:.0f} '
                    f'right={state["right"]:.0f} bottom={state["bottom"]:.0f})')

    def test_the_panel_is_not_buried_under_the_drawer(self):
        """On a narrow window the drawer is the only way to reach the footer
        icons, so the panel one of them opens would appear underneath it --
        dimmed by the backdrop and half covered by the menu."""
        self.open_page()
        self.set_viewport(400, 800)
        self.assertTrue(self.ensure_menu_visible())
        self.open_panel()

        self.assertFalse(
            self.js("return document.body.classList"
                    "  .contains('sidebar-open');"),
            'the drawer stayed open over the panel it had just opened')
        self.assert_clickable('[id^=content_tm_]', message='the help panel')

    def test_the_panel_still_stays_below_its_own_modal(self):
        """Guarded in test_help.py too, but helper_widget.js is edited here."""
        self.open_page()
        self.assertTrue(self.ensure_menu_visible())
        self.open_panel()
        self.js("document.querySelector('[id^=show_help_]').click();")
        self.wait_js("return document.querySelectorAll('.help_i').length > 0;")
        self.js("document.querySelector('.help_i').click();")
        self.wait_js(
            "const m = document.querySelector('[id^=modal_tm_]');"
            "return m && m.classList.contains('show');")

        layers = self.js(
            "const z = s => parseInt("
            "  getComputedStyle(document.querySelector(s)).zIndex, 10);"
            "return [z('[id^=content_tm_]'), z('[id^=modal_tm_]')];")
        self.assertLess(layers[0], layers[1],
                        'the help panel is drawn over the modal it opens')


@tag('selenium')
class TopMenuTest(MenuTestBase):
    """The navbar menu, which had the same two problems: hover-only and off-screen."""

    def open_top_menu(self):
        """Expand the navbar collapse, if this width collapses it at all.

        Above 992px ``navbar-expand-lg`` keeps the bar open without ever adding
        ``.show``, so testing for that class would press the toggler and fold
        away a menu that was already there. Ask whether the entry is laid out
        instead.
        """
        self.js(
            "const a = document.querySelector(arguments[0]);"
            "if (!a || a.getClientRects().length === 0) {"
            "  document.querySelector('.menu-top-navbar').click(); }",
            '#tm_%d' % self.top.pk)
        self.wait_js(
            "const a = document.querySelector('#tm_%d');"
            "return a && a.getClientRects().length > 0;" % self.top.pk,
            message='the top menu never became available')
        self.settle()

    def test_the_first_level_is_clickable_at_every_size(self):
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.open_top_menu()
                self.assert_clickable('#tm_%d' % self.top.pk,
                                      message=f'[{label}]')

    def open_top_branch(self, item, menu_selector):
        """Open one level of the navbar menu, if it is not open already.

        Idempotent, like the sidebar's: these are toggles, so clicking an open
        one folds it shut -- which is what a loop over viewport sizes does if
        it just clicks each time round.
        """
        already = self.js(
            "const m = document.querySelector(arguments[0]);"
            "return !!m && m.classList.contains('show');", menu_selector)
        if not already:
            self.js('document.querySelector(arguments[0]).click();',
                    '#tm_%d' % item.pk)
        self.wait_js(
            "const m = document.querySelector(arguments[0]);"
            "return !!m && m.classList.contains('show')"
            "       && m.getBoundingClientRect().height > 0;",
            menu_selector,
            message='%r never opened' % item.title)
        self.settle()

    def test_the_nested_level_opens_by_click_and_stays_on_screen(self):
        """It only ever opened on :hover, and `left: -110%` pushed it off."""
        self.open_page()
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.open_top_menu()
                self.open_top_branch(self.top, '#m_%d' % self.top.pk)
                self.open_top_branch(self.top_level1,
                                     '#m_%d' % self.top_level1.pk)
                for child in self.top_level2:
                    self.assert_reachable('#tm_%d' % child.pk,
                                          message=f'[{label}]')

    def test_the_expanded_bar_uses_the_whole_width(self):
        """It was floated right and shrink-wrapped: 112px of a 369px window,
        211px of empty grey beside it, and a dropdown laid out from that edge
        ran off the screen with no room left for a third level."""
        self.open_page()
        for label, width, height in SIZES:
            if width >= 992:
                continue
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.open_top_menu()
                bar = self.element_state('#navbarNavDropdown')
                # 0.8, not 0.95: the navbar keeps its own horizontal padding,
                # so "full width" lands around 87%. What this has to separate
                # is that from the shrink-wrapped 30% it used to be.
                self.assertGreaterEqual(
                    bar['width'], width * 0.8,
                    f'[{label}] the expanded bar is {bar["width"]:.0f}px of a '
                    f'{width}px window, wasting the rest')
                self.assertLess(
                    bar['left'], width * 0.1,
                    f'[{label}] the expanded bar starts {bar["left"]:.0f}px in '
                    f'instead of using the left of the window')

    def test_every_nested_level_is_reachable_at_every_size(self):
        """The whole branch open at once, to the depth ``demomenu`` ships.

        Each level is drawn by this project rather than by Bootstrap, so each
        one can break on its own -- and the third was the first to escape a
        parent that scrolls, which clipped it out of existence entirely.
        """
        self.open_page()
        chain = (
            (self.top, '#m_%d' % self.top.pk),
            (self.top_level1, '#m_%d' % self.top_level1.pk),
            (self.top_level2[0], '#m_%d' % self.top_level2[0].pk),
            (self.top_level3[0], '#m_%d' % self.top_level3[0].pk),
        )
        deepest = (self.top_level1, self.top_level2[0], self.top_level3[0],
                   self.top_level4[-1])
        for label, width, height in SIZES:
            with self.subTest(case=label):
                self.set_viewport(width, height)
                self.open_top_menu()
                for item, menu in chain:
                    self.open_top_branch(item, menu)

                for item in deepest:
                    state = self.assert_reachable(
                        '#tm_%d' % item.pk, message=f'[{label}]')
                    self.assertLessEqual(
                        state['right'], width + 1,
                        f'[{label}] {item.title!r} runs '
                        f'{state["right"] - width:.0f}px off the right edge')
                self.assert_no_horizontal_scroll(message=f'[{label}] ')

    def test_the_layout_follows_the_window_not_the_physical_screen(self):
        """custom.js read `screen.width`, so resizing the window changed nothing."""
        self.open_page()
        self.set_viewport(1500, 1100)
        wide = self.js(
            "return document.querySelector('#items-top-navbar')"
            "  .classList.contains('flex-row-reverse');")
        self.set_viewport(400, 800)
        narrow = self.js(
            "return document.querySelector('#items-top-navbar')"
            "  .classList.contains('flex-row-reverse');")
        self.assertNotEqual(
            wide, narrow,
            'the top navbar layout never reacted to the window being resized')


@tag('selenium')
class MenuConsoleTest(MenuTestBase):

    def test_the_page_reports_no_javascript_error(self):
        self.driver.get_log('browser')
        self.open_page()
        for _, width, height in SIZES:
            self.set_viewport(width, height)
            self.ensure_menu_visible()
        self.toggle_menu()

        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])
