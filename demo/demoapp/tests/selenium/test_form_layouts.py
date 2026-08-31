"""Browser tests for the four GTForm render strategies.

``as_plain``, ``as_inline``, ``as_horizontal`` and ``as_grid`` each wrap the
same fields in a different bootstrap structure. Rendering them in a browser --
rather than asserting on a template string -- is what catches a layout that
produces markup bootstrap cannot lay out: a column that never gets a width, a
label outside its row, a grid that collapses to one column.

``as_grid`` needs a ``grid_representation`` and no demo page supplies one, so
these tests swap in :mod:`demoapp.tests.selenium.layouts_urls`, which serves one
page per layout for exactly this purpose.
"""

from django.test import override_settings, tag

from .base import SeleniumTestCase

URLCONF = 'demoapp.tests.selenium.layouts_urls'
FIELDS = ('name', 'email', 'age', 'city')


@tag('selenium')
@override_settings(ROOT_URLCONF=URLCONF)
class FormLayoutTest(SeleniumTestCase):

    def open_layout(self, layout):
        self.go(f'/layouts/{layout}/')
        self.wait_js(
            "return !!document.querySelector('#the-form')",
            message=f'the {layout} page did not render a form')

    def field_ids(self):
        return self.js(
            "return Array.from(document.querySelectorAll("
            "'#the-form input, #the-form select, #the-form textarea'))"
            ".map(e => e.id).filter(Boolean);")

    def test_every_layout_renders_every_field(self):
        """Whatever the wrapper, no field may go missing."""
        for layout in ('as_plain', 'as_inline', 'as_horizontal', 'as_grid'):
            with self.subTest(layout=layout):
                self.open_layout(layout)
                ids = self.field_ids()
                for field in FIELDS:
                    self.assertIn(
                        f'id_{field}', ids,
                        f'{layout} dropped the {field} field')

    def test_every_layout_labels_every_field(self):
        """A label whose ``for`` points nowhere is a broken layout."""
        for layout in ('as_plain', 'as_inline', 'as_horizontal', 'as_grid'):
            with self.subTest(layout=layout):
                self.open_layout(layout)
                orphans = self.js(
                    "return Array.from(document.querySelectorAll("
                    "'#the-form label[for]'))"
                    ".map(l => l.getAttribute('for'))"
                    ".filter(f => !document.getElementById(f));")
                self.assertEqual(
                    orphans, [],
                    f'{layout} has labels pointing at missing fields')

    def test_horizontal_puts_the_label_and_the_field_in_one_row(self):
        self.open_layout('as_horizontal')
        rows = self.js(
            "return Array.from(document.querySelectorAll("
            "'#the-form .ashorizontal')).map(r => ({"
            "  isRow: r.classList.contains('row'),"
            "  label: !!r.querySelector('label.col-form-label'),"
            "  labelCol: !!r.querySelector('[class*=col-sm-]'),"
            "}));")
        self.assertTrue(rows, 'as_horizontal produced no .ashorizontal rows')
        for row in rows:
            self.assertTrue(row['isRow'], 'a horizontal row is not a .row')
            self.assertTrue(row['label'], 'a horizontal row has no col label')
            self.assertTrue(
                row['labelCol'], 'a horizontal row has no bootstrap columns')

    def test_horizontal_columns_sit_side_by_side(self):
        """The point of the horizontal layout: label beside field, not above.

        Compares the rendered geometry, which is the only way to tell a real
        bootstrap row from markup that merely carries the class names.
        """
        self.open_layout('as_horizontal')
        side_by_side = self.js(
            "const row = document.querySelector('#the-form .ashorizontal');"
            "const l = row.querySelector('label');"
            "const f = row.querySelector('input');"
            "if (!l || !f) return null;"
            "const lb = l.getBoundingClientRect();"
            "const fb = f.getBoundingClientRect();"
            "return fb.left > lb.left && Math.abs(fb.top - lb.top) < 40;")
        self.assertTrue(
            side_by_side,
            'the horizontal layout stacked the label above the field')

    def test_inline_puts_the_fields_in_columns_of_one_row(self):
        self.open_layout('as_inline')
        cols = self.js(
            "return document.querySelectorAll("
            "'#the-form .row > .col.asinline').length;")
        self.assertEqual(
            cols, len(FIELDS),
            'as_inline did not put every field in its own column')

    def test_plain_wraps_each_field_without_grid_classes(self):
        # The wrapper class comes from forms/as_plain.html and is `asplain`,
        # matching `asinline`/`ashorizontal`. GTForm.as_plain also carries a
        # branch emitting class="as_plain", but it is guarded by
        # hasattr(self, '_html_output') and django removed _html_output in 5.0,
        # so it is dead on every version this package supports.
        self.open_layout('as_plain')
        wrappers = self.js(
            "return document.querySelectorAll('#the-form .asplain').length;")
        self.assertEqual(
            wrappers, len(FIELDS),
            'as_plain did not wrap every field in an .asplain block')
        self.assertEqual(
            self.js("return document.querySelectorAll("
                    "'#the-form .asplain .col-sm-2').length;"),
            0, 'as_plain leaked the horizontal grid classes')

    def test_grid_follows_the_declared_representation(self):
        """``grid_representation`` is two rows of two columns.

        The whole contract of as_grid is that the author's matrix is what gets
        rendered; anything else silently rearranges the form.
        """
        self.open_layout('as_grid')
        shape = self.js(
            "return Array.from(document.querySelectorAll('#the-form .row'))"
            ".map(r => r.querySelectorAll(':scope > div').length)"
            ".filter(n => n > 0);")
        self.assertTrue(shape, 'as_grid rendered no rows')
        self.assertEqual(
            shape[:2], [2, 2],
            f'as_grid did not honour the 2x2 representation: {shape}')

    def test_grid_keeps_the_declared_field_order(self):
        self.open_layout('as_grid')
        order = [i for i in self.field_ids() if i.startswith('id_')]
        self.assertEqual(
            order, ['id_name', 'id_email', 'id_age', 'id_city'],
            'as_grid reordered the fields')
