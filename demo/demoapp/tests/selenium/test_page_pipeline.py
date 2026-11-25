"""The order page of the pipeline demo (``shop_orders.json``) in the browser:
an order for more than the stock shows the error of the validation and saves
nothing; a good one is saved with its total, takes the stock and the branch
goes to the ``shop_order_done`` page."""
import json
from decimal import Decimal

from django.test import tag

from demoapp.models import ShopItem, ShopOrder
from djgentelella.designs import engine, factories, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase


@tag('selenium')
class PagePipelineTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        self.backpack = ShopItem.objects.create(name='Backpack',
                                                price=Decimal('28.00'), stock=3)
        for name in ('shop_order_done', 'shop_orders'):
            with open(DEMO_DESIGNS / ('%s.json' % name)) as stream:
                _page, errors = publishing.publish(json.load(stream))
            self.assertEqual(errors, [])

    def open_create(self):
        self.go('/designs/shop-orders/')
        link = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-gtdesign="orders"] a.btn-outline-success')))
        self.driver.get(link.get_attribute('href'))
        self.wait.until(EC.presence_of_element_located((By.ID, 'id_quantity')))

    def send(self, quantity):
        self.js("jQuery('#id_item').val(arguments[0]).trigger('change');",
                str(self.backpack.pk))
        field = self.driver.find_element(By.ID, 'id_quantity')
        field.clear()
        field.send_keys(str(quantity))
        self.js("document.getElementById('id_quantity').form.requestSubmit();")

    def test_more_than_the_stock_is_refused(self):
        self.open_create()
        self.send(5)
        # The error of demoapp.check_stock, on the quantity: in English or in
        # Spanish, it names the item and the stock left.
        error = self.wait_js(
            "var found = Array.from(document.querySelectorAll("
            "'.errorlist, .invalid-feedback, .text-danger')).filter(function (e) {"
            "  return e.innerText.indexOf('Backpack') !== -1; });"
            "return found.length ? found[0].innerText : null;",
            message='the error of the validation never showed')
        self.assertIn('3', error)
        self.assertIn('/create/', self.driver.current_url)
        self.assertFalse(ShopOrder.objects.exists())
        self.assertEqual(ShopItem.objects.get(pk=self.backpack.pk).stock, 3)

    def test_an_order_is_saved_and_goes_to_the_next_page(self):
        self.open_create()
        self.send(2)
        self.wait.until(EC.presence_of_element_located((By.ID, 'order-done')))
        self.assertTrue(self.driver.current_url.endswith('/designs/shop-orders/done'),
                        self.driver.current_url)
        order = ShopOrder.objects.get()
        self.assertEqual((order.quantity, order.total), (2, Decimal('56.00')))
        self.assertEqual(ShopItem.objects.get(pk=self.backpack.pk).stock, 1)
        # The page the branch went to lists the stock left.
        self.wait.until(EC.text_to_be_present_in_element(
            (By.CSS_SELECTOR, '[data-gtdesign="stock"]'), 'Backpack'))


@tag('selenium')
class TablePipelineTest(SeleniumTestCase):
    """The same pipeline on an ``object_management`` table: the modal shows
    the error of the validation, and after a save the page follows the
    branch the API answers (``gtdesign_redirect``)."""

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        self.backpack = ShopItem.objects.create(name='Backpack',
                                                price=Decimal('28.00'), stock=3)
        with open(DEMO_DESIGNS / 'shop_order_done.json') as stream:
            _page, errors = publishing.publish(json.load(stream))
        self.assertEqual(errors, [])
        with open(DEMO_DESIGNS / 'shop_orders.json') as stream:
            document = json.load(stream)
        crud = document['root']['children'][1]['children'][0]['children'][0]
        crud['type'] = 'object_management'
        for name in ('views', 'list_fields'):
            crud['props'].pop(name)
        _page, errors = publishing.publish(document, path='shop-orders-table')
        self.assertEqual(errors, [])

    def send(self, quantity):
        self.js("jQuery('#id_orders_create-item').val(arguments[0])"
                ".trigger('change');", str(self.backpack.pk))
        field = self.driver.find_element(By.ID, 'id_orders_create-quantity')
        field.clear()
        field.send_keys(str(quantity))
        self.driver.find_element(
            By.CSS_SELECTOR, '#orders_create_modal .formadd').click()

    def test_the_modal_shows_the_error_and_then_follows_the_branch(self):
        self.go('/designs/shop-orders-table')
        self.js("new bootstrap.Modal('#orders_create_modal').show();")
        self.wait.until(EC.visibility_of_element_located(
            (By.ID, 'id_orders_create-quantity')))
        self.send(5)
        self.wait_js(
            "return Array.from(document.querySelectorAll("
            "'#orders_create_modal .form_errors, #orders_create_modal "
            ".invalid-feedback')).some(function (e) {"
            "  return e.innerText.indexOf('Backpack') !== -1; });",
            message='the error of the validation never showed in the modal')
        self.assertFalse(ShopOrder.objects.exists())
        self.send(1)
        self.wait.until(EC.presence_of_element_located((By.ID, 'order-done')))
        self.assertEqual(ShopItem.objects.get(pk=self.backpack.pk).stock, 2)
        self.assertEqual(ShopOrder.objects.get().total, Decimal('28.00'))
