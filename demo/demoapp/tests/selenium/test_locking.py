"""Optimistic locking in the browser (``djgentelella.locking``): two tabs edit
the same row of an ``object_management`` table with ``optimistic_lock``; the
second to save is told the row changed, and reloads the form with the
current data without losing the modal."""
import json
from datetime import date
from decimal import Decimal

from django.test import tag

from demoapp.models import Product, ProductCategory
from djgentelella.designs import engine, factories, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase


def with_lock(node):
    """The demo design with ``optimistic_lock`` on its products table."""
    if node.get('type') == 'object_management' and node.get('id') == 'products':
        node['props']['optimistic_lock'] = True
        return True
    return any(with_lock(child) for child in node.get('children', []))


@tag('selenium')
class OptimisticLockTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        food = ProductCategory.objects.create(name='Food')
        for name, price in (('Apple', '2.00'), ('Bread', '4.00')):
            Product.objects.create(name=name, price=Decimal(price), status='active',
                                   category=food, available_since=date.today())
        with open(DEMO_DESIGNS / 'product_admin.json') as stream:
            document = json.load(stream)
        self.assertTrue(with_lock(document['root']))
        _page, errors = publishing.publish(document)
        self.assertEqual(errors, [])

    def row_index(self, text):
        return self.js(
            'var dt = jQuery("#products_table").DataTable(), name = arguments[0];'
            'var found = dt.rows().indexes().toArray().filter(function (i) {'
            '  return dt.row(i).data().name === name; });'
            'return found.length ? found[0] : null;', text)

    def open_update(self, name):
        self.go('/designs/products')
        self.wait_rows('#products_table', lambda rows: len(rows) == 2,
                       'the table never filled')
        self.js("call_obj_crud_event('products', 'update', arguments[0]);",
                self.row_index(name))
        field = self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_products_update-name')))
        self.wait.until(lambda d: field.get_attribute('value') == name,
                        'the update form was never filled')
        return field

    def save(self):
        self.driver.find_element(
            By.CSS_SELECTOR, '#products_update_modal .formadd').click()

    def test_the_second_tab_is_told_and_reloads(self):
        bread = Product.objects.get(name='Bread')
        first = self.driver.current_window_handle
        mine = self.open_update('Bread')

        # Another tab saves the same row first.
        self.driver.switch_to.new_window('tab')
        self.addCleanup(self.close_other_tabs, first)
        theirs = self.open_update('Bread')
        theirs.clear()
        theirs.send_keys('Rye bread')
        self.save()
        self.wait_rows('#products_table',
                       lambda rows: any('Rye bread' in row for row in rows),
                       'the first save never showed up')
        self.assertEqual(Product.objects.get(pk=bread.pk).name, 'Rye bread')

        # Back in the first tab, the form still has the old version.
        self.driver.switch_to.window(first)
        mine.clear()
        mine.send_keys('White bread')
        self.save()
        confirm = self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '.swal2-popup .swal2-confirm')),
            'the conflict was never shown')
        self.assertTrue(self.js(
            "return document.querySelector('.swal2-popup')"
            "  .classList.contains('swal2-icon-warning') ||"
            " document.querySelector('.swal2-icon.swal2-warning') !== null;"))
        # Nothing was overwritten, and the modal is still open.
        self.assertEqual(Product.objects.get(pk=bread.pk).name, 'Rye bread')
        self.assertTrue(self.driver.find_element(
            By.ID, 'products_update_modal').is_displayed())

        confirm.click()
        self.wait.until(lambda d: mine.get_attribute('value') == 'Rye bread',
                        'the form was not reloaded with the current data')
        self.wait_js("return document.querySelector('.swal2-container') === null",
                     message='the conflict dialog never went away')
        self.assertTrue(self.driver.find_element(
            By.ID, 'products_update_modal').is_displayed())

        # Now it saves: the form carries the current version.
        mine.clear()
        mine.send_keys('White bread')
        self.save()
        self.wait_rows('#products_table',
                       lambda rows: any('White bread' in row for row in rows),
                       'the second save never showed up')
        self.assertEqual(Product.objects.get(pk=bread.pk).name, 'White bread')

    def close_other_tabs(self, keep):
        for handle in self.driver.window_handles:
            if handle != keep:
                self.driver.switch_to.window(handle)
                self.driver.close()
        self.driver.switch_to.window(keep)
