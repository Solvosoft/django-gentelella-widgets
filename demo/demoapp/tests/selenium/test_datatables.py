"""Browser tests for the DataTables wrapper (``gentelella/js/datatables.js``).

The wrapper builds a second header row of per-column filters out of a custom
``type`` key, wires the toolbar buttons and translates DataTables' request into
the DRF one. None of that is visible from Python -- the server only ever sees
``offset``/``limit``/``ordering`` -- so it takes a browser to notice when a
DataTables upgrade renames a class or drops an API.
"""

from django.test import tag

from demoapp.models import Country, Person
from .base import By, SeleniumTestCase

TABLE = '#datatableelement'
FIRST_FILTER = TABLE + ' thead tr:nth-child(2) th:first-child input'


@tag('selenium')
class DataTableTest(SeleniumTestCase):
    """/datatable_view: five columns, one of each filter type."""

    def setup_data(self):
        country = Country.objects.create(name='Costa Rica')
        for number in range(12):
            Person.objects.create(
                name='Person %02d' % number, num_children=number % 3,
                country=country, born_date='1990-01-%02d' % (number + 1),
                last_time='2020-01-01 10:00:00')

    def open_table(self):
        self.go('/datatable_view')
        self.wait_js(
            'return jQuery.fn.dataTable.isDataTable(arguments[0])', TABLE,
            message='the table never became a DataTable')
        self.wait_rows(TABLE, lambda rows: len(rows) > 0,
                       'the first page never arrived')

    def test_the_first_page_is_served_and_paginated(self):
        self.open_table()

        # lengthMenu starts at 10 and setup_data created 12 people.
        self.assertEqual(len(self.rows_of(TABLE)), 10)
        self.assertEqual(
            self.js('return jQuery(arguments[0]).DataTable()'
                    '.page.info().recordsTotal', TABLE), 12)

    def test_the_layout_puts_every_control_on_the_page(self):
        """``dom`` became ``layout`` in DataTables 2, and every wrapper class
        it generates was renamed from ``dataTables_*`` to ``dt-*``."""
        self.open_table()

        for control in ('.dt-search', '.dt-length', '.dt-info', '.dt-paging',
                        '.dt-buttons'):
            self.assertTrue(
                self.js('return document.querySelectorAll(arguments[0])'
                        '.length > 0', control),
                f'{control} is not in the page')

    def test_the_filter_row_gets_one_control_per_column_type(self):
        """``addfilter`` clones the header and fills it from the column type."""
        self.open_table()
        self.wait_js(
            "return document.querySelectorAll("
            "  arguments[0] + ' thead tr').length === 2", TABLE,
            message='the filter row was never cloned')

        controls = self.js(
            "return Array.from(document.querySelectorAll("
            "  arguments[0] + ' thead tr:nth-child(2) th'))"
            "  .map(th => { const c = th.querySelector('input, select');"
            "               return c ? c.tagName.toLowerCase() + ':' +"
            "                          (c.type || '') : 'empty'; });",
            TABLE)
        # name (string), num_children (number), country (string), and the two
        # date columns, which are text inputs driven by daterangepicker.
        self.assertEqual(controls[:3], ['input:text', 'input:number', 'input:text'])
        self.assertEqual(controls[3:], ['input:text', 'input:text'])

    def filter_by(self, value):
        """Type into the first column filter in one go.

        Not ``send_keys``: the wrapper redraws on every keystroke, and ten
        overlapping XHRs against the live server's SQLite file make it answer
        500 to some of them -- a limit of the harness, not of the widget.
        """
        self.js("const input = document.querySelector(arguments[0]);"
                "input.value = arguments[1];"
                "input.dispatchEvent(new Event('change', {bubbles: true}));",
                FIRST_FILTER, value)

    def test_a_column_filter_reaches_the_server(self):
        self.open_table()

        self.filter_by('Person 01')

        self.wait_rows(
            TABLE, lambda rows: len(rows) == 1,
            'the column filter never narrowed the table down to one row')
        self.assertIn('Person 01', self.rows_of(TABLE)[0])

    def test_the_clear_filters_button_restores_the_full_page(self):
        self.open_table()
        self.filter_by('Person 01')
        self.wait_rows(TABLE, lambda rows: len(rows) == 1)

        self.driver.find_element(By.CSS_SELECTOR, '.dt-buttons button').click()

        self.wait_rows(TABLE, lambda rows: len(rows) == 10,
                       'Clear Filters did not bring the rows back')
        self.assertEqual(
            self.js('return document.querySelector(arguments[0]).value',
                    FIRST_FILTER), '')

    def test_sorting_a_column_asks_the_server_to_order(self):
        """``formatDataTableParams`` turns the DataTables order into DRF's."""
        self.open_table()

        self.driver.find_element(
            By.CSS_SELECTOR, TABLE + ' thead tr:first-child th:first-child').click()
        self.wait_rows(TABLE, lambda rows: rows and 'Person 00' in rows[0])

        self.driver.find_element(
            By.CSS_SELECTOR, TABLE + ' thead tr:first-child th:first-child').click()
        self.wait_rows(TABLE, lambda rows: rows and 'Person 11' in rows[0],
                       'the descending order never reached the server')

    def test_the_page_reports_no_javascript_error(self):
        # The driver is shared by the whole class and get_log drains what it
        # returns, so empty it before the page under test is opened.
        self.driver.get_log('browser')
        self.open_table()

        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])
