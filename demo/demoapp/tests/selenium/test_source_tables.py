"""Read-only tables over a data source that is not over a model of the
project (W23): ``object_management`` in list mode, filtered by a facets
panel, and a read-only ``interactive_grid``; and the calendar of the regions
in the language of the page."""
import json
from datetime import timedelta

from django.test import tag
from django.utils import timezone

from demoapp.models import Country, Meetup
from djgentelella.datasources.base import (
    Column, DataSource, register_datasource, unregister_datasource,
)
from djgentelella.designs import engine, publishing
from djgentelella.tests.Designs_Test import design, node
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import By, SeleniumTestCase

SOURCE = 'selenium.remote_countries'


class RemoteCountries(DataSource):
    """Rows djgentelella cannot write: no project model behind them."""

    name = SOURCE
    label = 'Remote countries'
    perms = []
    project_model = None

    def columns(self, request):
        return [Column('name', 'Name', 'string'), Column('code', 'Code', 'string')]

    def get_queryset(self, request, params=None):
        return Country.objects.all()


@tag('selenium')
class SourceTablesTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        register_datasource(RemoteCountries())
        self.addCleanup(unregister_datasource, SOURCE)
        for name, code in (('Costa Rica', 'cr'), ('Panama', 'pa'),
                           ('Nicaragua', 'ni')):
            Country.objects.create(name=name, code=code)
        document = design(
            node('object_management', 'countries', {
                'datasource': SOURCE, 'list_fields': ['name', 'code'],
                'ordering': ['name']}),
            node('facets', 'filters', {'target': 'countries', 'columns': ['code']}),
            node('interactive_grid', 'grid', {
                'datasource': SOURCE, 'columns': ['name', 'code'],
                'ordering': ['-name']}))
        _page, errors = publishing.publish(document, path='remote-countries')
        self.assertEqual(errors, [])

    def grid_names(self):
        return self.js("return Array.prototype.map.call(document.querySelectorAll("
                       "  '#grid_table tbody tr[data-key] td[data-column=\"name\"]'),"
                       "  function (td) { return td.textContent.trim(); });")

    def test_a_list_and_a_grid_that_only_read(self):
        self.go('/designs/remote-countries')
        table = '#countries_table'
        self.wait_rows(table, lambda rows: len(rows) == 3, 'the list never filled')
        self.assertTrue(self.rows_of(table)[0].startswith('Costa Rica'))
        # No modals, no column filters: it only reads.
        self.assertEqual(self.js("return document.querySelectorAll("
                                 "  '[id^=countries_][id$=_modal]').length"), 0)
        self.wait.until(lambda d: self.grid_names() == ['Panama', 'Nicaragua',
                                                        'Costa Rica'],
                        'the grid never filled')
        self.assertEqual(self.js("return document.querySelectorAll("
                                 "  '#grid_grid .gtgrid-save, #grid_grid .gtgrid-add,"
                                 "   #grid_grid .gtgrid-edit').length"), 0)
        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 1",
                     message='the facets never rendered')
        self.driver.find_element(
            By.XPATH, '//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                      '"code"]//label[starts-with(normalize-space(.), "pa")]').click()
        self.wait_rows(table, lambda rows: len(rows) == 1 and 'Panama' in rows[0],
                       'the list did not follow the facet')


@tag('selenium')
class CalendarLocaleTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        with open(DEMO_DESIGNS / 'meetups.json') as stream:
            _page, errors = publishing.publish(json.load(stream))
        self.assertEqual(errors, [])
        Meetup.objects.create(title='Volcano talk', kind='talk', city='Cartago',
                              starts_at=timezone.now() + timedelta(hours=1),
                              location='9.864400,-83.919400')

    def test_the_calendar_speaks_spanish(self):
        # The demo is served in Spanish (LANGUAGE_CODE = 'es').
        self.go('/designs/meetups/')
        self.wait_js("return !!document.querySelector("
                     "  '[data-gtdesign=\"meetup_calendar\"] .fc-today-button')",
                     message='the calendar never rendered')
        self.wait.until(lambda d: self.js(
            "return document.querySelector('[data-gtdesign=\"meetup_calendar\"] "
            ".fc-today-button').textContent.trim()") == 'Hoy',
            'the calendar is not in Spanish')
