"""Browser smoke tests of the components with data of djgentelella.designs:
the demo designs (``demoapp/gtdesign/``) published and served with no
generated code -- a table, its modals and its facets, charts, stats and the
inline table of one parent."""
import json
from datetime import date
from decimal import Decimal

from django.test import tag

from demoapp.models import Product, ProductCategory, ProductTag
from djgentelella.designs import engine, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase


@tag('selenium')
class DesignDataComponentsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        self.food = ProductCategory.objects.create(name='Food')
        self.tools = ProductCategory.objects.create(name='Tools')
        red = ProductTag.objects.create(name='red')
        rows = [('Apple', '2.00', 'active', self.food),
                ('Bread', '4.00', 'draft', self.food),
                ('Hammer', '30.00', 'active', self.tools)]
        for name, price, status, category in rows:
            product = Product.objects.create(
                name=name, price=Decimal(price), status=status, category=category,
                available_since=date.today())
            product.tags.add(red)
        for name in ('category_products', 'product_admin', 'sales_dashboard'):
            with open(DEMO_DESIGNS / ('%s.json' % name)) as stream:
                _page, errors = publishing.publish(json.load(stream))
            self.assertEqual(errors, [])

    def chart_labels(self, node_id):
        return self.js(
            "var canvas = document.querySelector("
            "  '[data-gtdesign=\"' + arguments[0] + '\"] canvas');"
            "var chart = canvas && Chart.getChart(canvas);"
            "return chart ? chart.data.labels : null;", node_id)

    def test_a_page_with_a_table_and_charts(self):
        self.go('/designs/dashboard')
        self.wait_rows('#categories_table_table', lambda rows: len(rows) == 2,
                       'the categories table never filled')
        self.assertTrue(any('Food' in row for row in
                            self.rows_of('#categories_table_table')))
        self.wait.until(lambda d: self.chart_labels('by_category') == ['Food', 'Tools'],
                        'the bar chart never drew the real data')
        self.wait.until(lambda d: sorted(self.chart_labels('by_status') or [])
                        == ['Active', 'Draft'], 'the pie chart never drew')
        tile = self.driver.find_element(
            By.CSS_SELECTOR, '[data-gtdesign="categories"] .count')
        self.assertEqual(tile.text, '2')

    def test_create_in_the_modal_and_filter_with_the_facets(self):
        self.go('/designs/products')
        table = '#products_table'
        self.wait_rows(table, lambda rows: len(rows) == 3, 'the table never filled')
        self.js("new bootstrap.Modal('#products_create_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_products_create-name')))
        self.driver.find_element(By.ID, 'id_products_create-name').send_keys(
            '<b>Saw</b>')
        price = self.driver.find_element(By.ID, 'id_products_create-price')
        price.clear()
        price.send_keys('12')
        self.driver.find_element(
            By.CSS_SELECTOR, '#products_create_modal .formadd').click()
        self.wait_rows(table, lambda rows: len(rows) == 4,
                       'the new row never showed up')
        self.assertTrue(Product.objects.filter(name='<b>Saw</b>').exists())
        # Shown as text: the renderers escape what the rows carry.
        self.assertIn('<b>Saw</b>', ' '.join(self.rows_of(table)))
        self.assertEqual(self.js(
            "return document.querySelectorAll(arguments[0] + ' tbody b').length",
            table), 0)

        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 4",
                     message='the facets never rendered')
        # The "saved" toast of the create modal covers the panel a moment.
        self.wait_js("return document.querySelector('.swal2-container') === null",
                     message='the saved toast never went away')
        self.driver.find_element(
            By.XPATH, '//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                      '"category"]//label[starts-with(normalize-space(.), "Tools")]'
        ).click()
        self.wait_rows(table, lambda rows: len(rows) == 1 and 'Hammer' in rows[0],
                       'the table did not follow the facet')

    def row_index(self, table, text):
        return self.js(
            'var dt = jQuery(arguments[0]).DataTable(), name = arguments[1];'
            'var found = dt.rows().indexes().toArray().filter(function (i) {'
            '  return dt.row(i).data().name === name; });'
            'return found.length ? found[0] : null;', table, text)

    def test_detail_update_and_delete_in_the_modals(self):
        self.go('/designs/products')
        table = '#products_table'
        self.wait_rows(table, lambda rows: len(rows) == 3, 'the table never filled')

        self.js("call_obj_crud_event('products', 'detail', arguments[0]);",
                self.row_index(table, 'Hammer'))
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'products_detail_modal')))
        self.wait_js("return document.querySelector('#products_detail_modal "
                     "  .modal-body').textContent.indexOf('Tools') >= 0",
                     message='the detail never showed the category')
        self.assertEqual(self.driver.find_element(
            By.CSS_SELECTOR, '#products_detail_modal .modal-title').text, 'Hammer')
        self.js("bootstrap.Modal.getInstance("
                "  document.getElementById('products_detail_modal')).hide();")
        self.wait.until(EC.invisibility_of_element_located(
            (By.ID, 'products_detail_modal')))

        self.js("call_obj_crud_event('products', 'update', arguments[0]);",
                self.row_index(table, 'Bread'))
        name = self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_products_update-name')))
        self.wait.until(lambda d: name.get_attribute('value') == 'Bread',
                        'the update form was never filled')
        name.clear()
        name.send_keys('Rye bread')
        self.driver.find_element(
            By.CSS_SELECTOR, '#products_update_modal .formadd').click()
        self.wait_rows(table, lambda rows: any('Rye bread' in row for row in rows),
                       'the updated row never showed up')
        self.assertTrue(Product.objects.filter(name='Rye bread').exists())

        self.wait.until(EC.invisibility_of_element_located(
            (By.ID, 'products_update_modal')))
        self.js("call_obj_crud_event('products', 'destroy', arguments[0]);",
                self.row_index(table, 'Apple'))
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'products_delete_modal')))
        self.driver.find_element(
            By.CSS_SELECTOR, '#products_delete_modal .delbtn').click()
        self.wait_rows(table, lambda rows: len(rows) == 2,
                       'the deleted row is still there')
        self.assertFalse(Product.objects.filter(name='Apple').exists())

    def test_search_and_column_filters(self):
        self.go('/designs/products')
        table = '#products_table'
        self.wait_rows(table, lambda rows: len(rows) == 3, 'the table never filled')
        self.js("jQuery(arguments[0]).DataTable().search('ham').draw();", table)
        self.wait_rows(table, lambda rows: len(rows) == 1 and 'Hammer' in rows[0],
                       'the search did not narrow the table')
        self.js("jQuery(arguments[0]).DataTable().search('').column('status:name')"
                "  .search('draft').draw();", table)
        self.wait_rows(table, lambda rows: len(rows) == 1 and 'Bread' in rows[0],
                       'the column filter did not narrow the table')

    def test_the_inline_table_of_one_parent(self):
        self.go('/designs/category-products/%d' % self.food.pk)
        self.wait_rows('#products_table', lambda rows: len(rows) == 2,
                       'the inline table never filled')
        names = ' '.join(self.rows_of('#products_table'))
        self.assertIn('Apple', names)
        self.assertNotIn('Hammer', names)
