"""The help palette, the menu widget that hangs contextual help off form labels.

It is a menu widget, so it only exists once a ``MenuItem`` points at it -- which
is why none of this was covered: the demo's menu is built by a management
command the test suite never runs.

The panel builds each entry by cloning a prototype block of markup and swapping
``$title``/``$text`` placeholders into it. That prototype has to stay in the
page and stay invisible, which is the part that broke: it was hidden with
``class="hidden"``, a Bootstrap 3 utility that Bootstrap 4 dropped and nothing
in this project defines, so the raw ``$title``, ``$byline`` and ``$text``
showed up inside the panel.
"""

from django.test import tag
from django.urls import reverse

from djgentelella.models import Help, MenuItem
from .base import SeleniumTestCase

FORM_PAGE = '/knobwidget/testform'
FIELD = 'id_age'


@tag('selenium')
class HelpPaletteTest(SeleniumTestCase):

    def setup_data(self):
        self.menu_item = MenuItem.objects.create(
            parent=None, title='', category='sidebarfooter',
            url_name='djgentelella.menu_widgets.palette.PalleteWidget',
            is_reversed=False, reversed_kwargs=None,
            reversed_args=reverse('help'), is_widget=True,
            icon='fa fa-question-circle', only_icon=True)
        self.help = Help.objects.create(
            id_view='knobwidgets', question_name=FIELD,
            help_title='Sobre la edad',
            help_text='Escriba la edad en años cumplidos.')

    def open_page(self):
        self.go(FORM_PAGE)
        self.wait_js(
            "return typeof document.help_widget === 'object'"
            "  && document.querySelectorAll('#helper-body').length > 0;",
            message='the help palette never rendered')

    def open_panel(self):
        self.open_page()
        self.js("document.querySelector('#fsb_' + arguments[0]).click();",
                self.menu_item.pk)
        self.wait_js(
            "const p = document.querySelector('[id^=content_tm_]');"
            "return p && p.classList.contains('show');",
            message='the help panel never opened')

    def test_the_prototype_stays_out_of_sight(self):
        self.open_page()

        prototype = self.js(
            "const p = document.querySelector('#helper-prototype');"
            "if (!p) return null;"
            "return [getComputedStyle(p).display,"
            "        p.innerHTML.indexOf('$title') !== -1];")
        self.assertIsNotNone(prototype, 'the prototype block is not in the page')
        self.assertEqual(prototype[0], 'none',
                         'the prototype is visible: its placeholders leak into '
                         'the panel as literal $title / $byline / $text')
        self.assertTrue(prototype[1],
                        'the prototype lost its placeholders, so nothing can be '
                        'built from it')

    def test_no_placeholder_is_ever_shown(self):
        self.open_panel()

        panel = self.js(
            "return document.querySelector('[id^=content_tm_]').innerText;")
        for placeholder in ('$title', '$text', '$byline'):
            self.assertNotIn(placeholder, panel,
                             f'{placeholder} is visible in the help panel')

    def test_a_stored_entry_is_listed_with_its_text(self):
        self.open_panel()

        self.wait_js(
            "return document.querySelectorAll('#helper-body .helperitem')"
            "  .length === 1;",
            message='the stored help entry was never listed')
        item = self.js(
            "const i = document.querySelector('#helper-body .helperitem');"
            "return [i.querySelector('.title').textContent.trim(),"
            "        i.querySelector('.excerpt').textContent.trim()];")
        self.assertEqual(item[0], 'Sobre la edad')
        self.assertIn('años cumplidos', item[1])

    def test_the_field_it_documents_gets_its_question_mark(self):
        """What makes the help contextual: the icon lands on that field's label."""
        self.open_page()

        self.wait_js(
            'const l = document.querySelector("label[for=" + '
            'JSON.stringify(arguments[0]) + "]");'
            "return l && l.closest('.helpbtn') !== null"
            "  && l.closest('.helpbtn').querySelector('.help_i') !== null;",
            FIELD, message='the label of the documented field has no help icon')

    def open_write_modal(self):
        """The flow from the screenshot: press +, then a field's question mark."""
        self.open_panel()
        self.js("document.querySelector('[id^=show_help_]').click();")
        self.wait_js("return document.querySelectorAll('.help_i').length > 0;",
                     message='pressing + never offered the fields')
        self.js("document.querySelector('.help_i').click();")
        self.wait_js(
            "const m = document.querySelector('[id^=modal_tm_]');"
            "return m && m.classList.contains('show');",
            message='the help modal never opened')

    def test_the_write_modal_says_what_it_is_for(self):
        """It opened with an empty title bar and an empty box, which said
        nothing about what to write or where it would show up."""
        self.open_write_modal()

        modal = self.js(
            "const m = document.querySelector('[id^=modal_tm_]');"
            "const hint = m.querySelector('.helper-modal-hint');"
            "return [m.querySelector('.modal-title').textContent.trim(),"
            "        hint ? hint.textContent.trim().length : 0];")
        self.assertTrue(modal[0], 'the modal still has no title')
        self.assertGreater(modal[1], 40,
                           'the modal does not explain how to write a help entry')

    def test_the_panel_does_not_cover_its_own_modal(self):
        """The panel is pinned with a z-index of its own; it used to be 10000,
        which is above every modal Bootstrap draws."""
        self.open_write_modal()

        layers = self.js(
            "const z = sel => parseInt(getComputedStyle("
            "  document.querySelector(sel)).zIndex, 10);"
            "return [z('[id^=content_tm_]'), z('[id^=modal_tm_]')];")
        self.assertLess(layers[0], layers[1],
                        'the help panel is drawn over the modal it opens')

    def test_the_empty_panel_explains_how_to_start(self):
        Help.objects.all().delete()
        self.open_panel()

        empty = self.js(
            "const e = document.querySelector('.helper-empty');"
            "return e ? [getComputedStyle(e).display, e.textContent.trim().length]"
            "         : null;")
        self.assertIsNotNone(empty, 'there is no empty state in the panel')
        self.assertNotEqual(empty[0], 'none',
                            'the empty state is hidden when there is no help')
        self.assertGreater(empty[1], 40, 'the empty state explains nothing')

    def test_the_empty_state_steps_aside_once_there_is_help(self):
        self.open_panel()

        self.wait_js(
            "return document.querySelectorAll('#helper-body .helperitem')"
            "  .length === 1;")
        self.assertEqual(
            self.js("return getComputedStyle("
                    "  document.querySelector('.helper-empty')).display;"),
            'none', 'the empty state is still shown next to a real entry')

    def test_the_page_reports_no_javascript_error(self):
        self.driver.get_log('browser')
        self.open_panel()

        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])
