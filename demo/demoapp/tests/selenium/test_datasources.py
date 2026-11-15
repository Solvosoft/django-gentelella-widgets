"""Browser tests of the data source widgets (``gentelella/js/base/gt_facets.js``)
on the demo page ``/datasources/``: the table, the facets panel, the chips and
the export menu share one parameter document and reload each other."""
import json
from urllib.parse import parse_qs, urlparse

from django.test import tag

from demoapp.models import Country, Person
from .base import By, SeleniumTestCase

TABLE = '#datasourcetable'
FACETS = '[data-widget="GTFacets"]'
CHIPS = '[data-widget="GTFacetChips"]'


@tag('selenium')
class DataSourceWidgetsTest(SeleniumTestCase):

    def setup_data(self):
        cr = Country.objects.create(name='Costa Rica')
        pa = Country.objects.create(name='Panama')
        for number in range(12):
            Person.objects.create(
                name='Person %02d' % number, num_children=number % 4,
                country=pa if number < 3 else cr,
                born_date='1990-01-%02d' % (number + 1),
                last_time='2020-01-01 10:00:00')

    def open_page(self):
        self.go('/datasources/')
        self.wait_rows(TABLE, lambda rows: len(rows) == 10,
                       'the first page never arrived')
        self.wait_js("return document.querySelectorAll("
                     "  arguments[0] + ' .gt-facet').length === 3", FACETS,
                     message='the facets never rendered')

    def facet_labels(self, column):
        return self.js(
            "return Array.from(document.querySelectorAll(arguments[0] +"
            "  ' .gt-facet[data-column=\"' + arguments[1] + '\"] label'))"
            "  .map(l => l.textContent);", FACETS, column)

    def test_facets_filter_the_table_and_count_without_their_own_filter(self):
        self.open_page()
        self.assertEqual(sorted(self.facet_labels('country')),
                         ['Costa Rica (9)', 'Panama (3)'])
        self.driver.find_element(
            By.XPATH, '//div[@data-widget="GTFacets"]//label[starts-with('
                      'normalize-space(.), "Panama")]').click()
        self.wait_rows(TABLE, lambda rows: len(rows) == 3,
                       'the table did not follow the facet')
        self.assertTrue(all('Panama' in row for row in self.rows_of(TABLE)))
        # Its own facet still offers the other country...
        self.wait_js("return Array.from(document.querySelectorAll("
                     "  arguments[0] + ' .gt-facet[data-column=\"num_children\"]"
                     "  label')).map(l => l.textContent).join() === "
                     "  arguments[1]", FACETS, '0 (1),1 (1),2 (1)',
                     message='the other facets did not recount')
        self.assertEqual(sorted(self.facet_labels('country')),
                         ['Costa Rica (9)', 'Panama (3)'])
        # ...the chips show the filter, and removing it restores the table.
        self.wait_js("return document.querySelector(arguments[0] +"
                     "  ' .gt-facet-chip') !== null", CHIPS)
        chip = self.driver.find_element(By.CSS_SELECTOR, CHIPS + ' .gt-facet-chip')
        self.assertIn('Panama', chip.text)
        chip.find_element(By.CSS_SELECTOR, '.btn-close').click()
        self.wait_rows(TABLE, lambda rows: len(rows) == 10,
                       'removing the chip did not clear the filter')

    def test_export_carries_the_current_parameters(self):
        self.open_page()
        self.driver.find_element(
            By.XPATH, '//div[@data-widget="GTFacets"]//label[starts-with('
                      'normalize-space(.), "Costa Rica")]').click()
        self.wait_rows(TABLE, lambda rows: len(rows) == 9,
                       'the table did not follow the facet')
        url = self.js("return Object.values(document.gt_datasource_states)[0]"
                      "  .exportUrl('xlsx')")
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query['fmt'], ['xlsx'])
        params = json.loads(query['params'][0])
        self.assertEqual(params['filters'][0]['column'], 'country')
        self.assertEqual(params['columns'][:2], ['name', 'num_children'])
        formats = self.js("return Array.from(document.querySelectorAll("
                          "  '.gt-datasource-export [data-format]'))"
                          "  .map(a => a.dataset.format)")
        self.assertEqual(formats, ['csv', 'xlsx', 'json', 'pdf'])
        # The browser's own session downloads it.
        answer = self.driver.execute_async_script(
            "const done = arguments[arguments.length - 1];"
            "fetch(arguments[0], {credentials: 'same-origin'})"
            "  .then(r => done([r.status, r.headers.get('Content-Type')]));", url)
        self.assertEqual(answer[0], 200)
        self.assertIn('spreadsheetml', answer[1])

    def test_the_table_menu_lists_the_builtin_formats_first(self):
        """The info endpoint lists the formats sorted; the table's export
        menu shows csv, xlsx, json, pdf first, then the rest by name."""
        self.open_page()
        self.assertEqual(self.js(
            "return gt_datasource_menu_formats(['pdf:b', 'csv', 'json', 'pdf',"
            "  'pdf:a', 'xlsx'])"), ['csv', 'xlsx', 'json', 'pdf', 'pdf:a', 'pdf:b'])
        self.assertEqual(self.js("return gt_datasource_menu_formats(['json', 'csv'])"),
                         ['csv', 'json'])
        # The export collection is the table's second button (after Clear).
        labels = self.js("var dt = $(arguments[0]).DataTable();"
                         "return [0, 1, 2, 3].map(i => dt.button('1-' + i).text())",
                         TABLE)
        self.assertEqual(labels, ['CSV', 'Excel', 'JSON', 'PDF'])

    def test_related_names_and_titles_are_escaped(self):
        """``display_name`` is ``str()`` of a related object, so users write
        it: the table shows it as text and never runs it."""
        payload = '<img src=x class="gt-xss" onerror="window.gtXss=1">'
        Person.objects.filter(country__name='Panama').update(
            country=Country.objects.create(name=payload))
        self.go('/datasources/')
        self.wait_rows(TABLE, lambda rows: len(rows) == 10,
                       'the first page never arrived')
        self.wait_rows(TABLE, lambda rows: any(payload in row for row in rows),
                       'the related name never showed as text')
        self.assertIsNone(self.js("return document.querySelector('.gt-xss')"))
        self.assertIsNone(self.js('return window.gtXss || null'))
        # Every renderer of the widget, called directly.
        rendered = self.js(
            "var p = arguments[0], out = {};"
            "['fk', 'm2m', 'string', 'choices', 'datetime'].forEach(function (k) {"
            "  var r = gt_datasource_render({kind: k, choices: [[p, p]]});"
            "  var value = k === 'fk' ? {display_name: p} :"
            "              k === 'm2m' ? [{display_name: p}, {display_name: p}] : p;"
            "  if (typeof r !== 'function') { r = r.display; }"
            "  out[k] = r(value, 'display', {}, {});"
            "});"
            "out.title = gt_datasource_columns({columns: [{name: 'x', label: p,"
            "  kind: 'string', sortable: true}]})[0].title;"
            "out.fkEmpty = gt_datasource_render({kind: 'fk'})(null, 'display');"
            "out.m2mEmpty = gt_datasource_render({kind: 'm2m'})([], 'display');"
            "return out;", payload)
        escaped = ('&lt;img src=x class=&quot;gt-xss&quot; '
                   'onerror=&quot;window.gtXss=1&quot;&gt;')
        # Chrome reads a date out of almost anything: only no markup counts.
        self.assertNotIn('<', rendered['datetime'])
        for kind in ('fk', 'string', 'choices', 'title'):
            with self.subTest(kind=kind):
                self.assertEqual(rendered[kind], escaped)
        self.assertEqual(rendered['m2m'], escaped + '<br>' + escaped)
        self.assertEqual(rendered['fkEmpty'], '---')
        self.assertEqual(rendered['m2mEmpty'], '---')
