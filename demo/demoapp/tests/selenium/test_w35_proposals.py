"""W35 in the browser: the master-detail of a design page read by the engine
-- the master of the page marked in its table, a click on another row opens
that master's page, ``gtdesign_select_row`` marks a row on demand -- and the
user menu of the top bar."""
from django.test import tag

from demoapp.models import ProductCategory
from djgentelella.designs import engine, factories, publishing
from djgentelella.models import MenuItem
from djgentelella.tests.Designs_Test import design, node

from .base import By, SeleniumTestCase

TABLE = '#categories_table'


@tag('selenium')
class MasterDetailTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        self.food = ProductCategory.objects.create(name='Food')
        self.tools = ProductCategory.objects.create(name='Tools')
        document = design(
            node('object_management', 'categories', {
                'model': 'demoapp.ProductCategory', 'form': 'category_form',
                'list_fields': ['name']}),
            forms={'category_form': {'model': 'demoapp.ProductCategory',
                                     'fields': ['name']}},
            url='w35-master/', url_name='w35-master',
            parent={'model': 'demoapp.ProductCategory'})
        document['root']['children'][0]['meta'] = {'master_detail': {
            'variant': 'stacked', 'master': 'categories'}}
        _page, errors = publishing.publish(document, path='w35-master')
        self.assertEqual(errors, [])

    def marked(self):
        return self.js(
            "return Array.from(document.querySelectorAll("
            "  arguments[0] + ' tbody tr.table-active[aria-selected=true]'))"
            "  .map(tr => tr.textContent.replace(/\\s+/g,' ').trim());", TABLE)

    def test_the_master_is_marked_and_a_click_chooses_another(self):
        self.go('/designs/w35-master/%d/' % self.food.pk)
        self.wait_rows(TABLE, lambda rows: len(rows) == 2, 'the masters never loaded')
        self.wait.until(lambda d: len(self.marked()) == 1
                        and 'Food' in self.marked()[0],
                        'the master of the page is not marked')
        # On demand, for generated code.
        count = self.js(
            "return window.gtdesign_select_row('categories', arguments[0]);",
            self.tools.pk)
        self.assertEqual(count, 1)
        self.assertIn('Tools', self.marked()[0])
        # A click on the text of a row (not its buttons) opens its page.
        cell = self.driver.find_element(
            By.XPATH, '//table[@id="categories_table"]//td[normalize-space(.)="Tools"]')
        self.mouse_click(cell)
        self.wait.until(lambda d: d.current_url.rstrip('/').endswith(
            '/designs/w35-master/%d' % self.tools.pk), 'the click opened nothing')
        self.wait_rows(TABLE, lambda rows: len(rows) == 2, 'the masters never loaded')
        self.wait.until(lambda d: len(self.marked()) == 1
                        and 'Tools' in self.marked()[0],
                        'the new master is not marked')


@tag('selenium')
class UserMenuTest(SeleniumTestCase):

    def setup_data(self):
        MenuItem.objects.create(key='w35-user-menu', title='User', category='main',
                                is_widget=True, url_name='gt-user-menu',
                                icon='fa fa-user', position=200)

    def test_open_the_menu_and_log_out(self):
        self.go('/')
        toggle = self.driver.find_element(By.CSS_SELECTOR, 'a.gt-user-menu')
        self.mouse_click(toggle)
        logout = self.driver.find_element(By.ID, 'gt-user-logout')
        self.wait.until(lambda d: logout.is_displayed(), 'the menu never opened')
        self.mouse_click(logout)
        self.wait.until(lambda d: 'gt-user-logout' not in d.page_source,
                        'the user was not logged out')
