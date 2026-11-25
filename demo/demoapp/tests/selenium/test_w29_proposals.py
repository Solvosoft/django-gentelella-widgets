"""W29 in the browser: a facets panel filters a read-only grid over a data
source, and a grid cell edited with a widget built from ``widget_options``."""
from django.test import tag

from demoapp.models import Country, WidgetShowcase
from djgentelella.datasources.base import register_datasource, unregister_datasource
from djgentelella.designs import engine, factories, publishing
from djgentelella.designs.exposure import expose, unexpose
from djgentelella.tests.Designs_Test import design, node

from .base import EC, By, SeleniumTestCase, WebDriverException
from .test_source_tables import SOURCE, RemoteCountries


@tag('selenium')
class GridFacetsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        register_datasource(RemoteCountries())
        self.addCleanup(unregister_datasource, SOURCE)
        for name, code in (('Costa Rica', 'cr'), ('Panama', 'pa'),
                           ('Nicaragua', 'ni')):
            Country.objects.create(name=name, code=code)
        document = design(
            node('facets', 'filters', {'target': 'grid', 'columns': ['code']}),
            node('interactive_grid', 'grid', {
                'datasource': SOURCE, 'columns': ['name', 'code'],
                'ordering': ['name']}))
        _page, errors = publishing.publish(document, path='grid-facets')
        self.assertEqual(errors, [])

    def grid_names(self):
        return self.js("return Array.prototype.map.call(document.querySelectorAll("
                       "  '#grid_table tbody tr[data-key] td[data-column=\"name\"]'),"
                       "  function (td) { return td.textContent.trim(); });")

    def click_facet(self, code):
        """Click the facet of ``code``; the panel draws its counts again after
        each click, so a label found before that is stale: find it again."""
        xpath = ('//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                 '"code"]//label[starts-with(normalize-space(.), "%s")]' % code)

        def click(driver):
            try:
                self.mouse_click(driver.find_element(By.XPATH, xpath))
            except WebDriverException:  # stale or not drawn yet
                return False
            return True

        self.wait.until(click, 'the facet %s could not be clicked' % code)

    def test_the_grid_follows_the_facets(self):
        self.go('/designs/grid-facets')
        self.wait.until(lambda d: self.grid_names() == ['Costa Rica', 'Nicaragua',
                                                        'Panama'],
                        'the grid never filled')
        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 1",
                     message='the facets never rendered')
        self.click_facet('pa')
        self.wait.until(lambda d: self.grid_names() == ['Panama'],
                        'the grid did not follow the facet')
        self.click_facet('ni')
        self.wait.until(lambda d: self.grid_names() == ['Nicaragua', 'Panama'],
                        'the grid did not add the second value')
        self.click_facet('pa')
        self.wait.until(lambda d: self.grid_names() == ['Nicaragua'],
                        'the grid did not drop the first value')
        self.click_facet('ni')
        self.wait.until(lambda d: len(self.grid_names()) == 3,
                        'the grid did not come back to every row')


@tag('selenium')
class WidgetOptionsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        expose(WidgetShowcase)
        self.addCleanup(unexpose, WidgetShowcase)
        self.item = WidgetShowcase.objects.create(name='Album', rating=2)
        document = design(node('interactive_grid', 'grid', {
            'model': 'demoapp.WidgetShowcase', 'columns': ['name', 'rating'],
            'editable': ['name', 'rating'],
            'widgets': {'rating': 'StarRatingInput'},
            'widget_options': {'rating': {'stars': 3}}}))
        _page, errors = publishing.publish(document, path='widget-options')
        self.assertEqual(errors, [])

    def test_a_cell_with_three_stars(self):
        self.go('/designs/widget-options')
        cell = '#grid_table tr[data-id="%d"] td[data-column="rating"]' % self.item.pk
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, cell)),
                        'the grid never filled')
        self.mouse_click(self.driver.find_element(By.CSS_SELECTOR, cell))
        self.wait_js("return document.querySelectorAll(arguments[0] + "
                     "' .gt-rating-star').length === 3", cell,
                     message='the cell is not a widget of three stars')
        self.mouse_click(self.driver.find_element(
            By.CSS_SELECTOR, cell + ' .gt-rating-star[data-value="3"]'))
        self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '#grid_grid .gtgrid-save'))).click()
        self.wait.until(lambda d: WidgetShowcase.objects.get(pk=self.item.pk).rating
                        == 3, 'the third star was not saved')
