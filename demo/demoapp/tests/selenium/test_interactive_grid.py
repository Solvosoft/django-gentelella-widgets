"""The interactive grid of djgentelella.designs in the browser: rows edited in
place with their widgets and saved together; a row somebody else saved in
between is marked, and reloading it keeps the changes of the other rows."""
import json
from datetime import date
from decimal import Decimal

from django.test import tag

from demoapp.models import Product, ProductCategory
from djgentelella.designs import engine, factories, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase

TABLE = '#product_grid_table'


@tag('selenium')
class InteractiveGridTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        factories.clear_cache()
        food = ProductCategory.objects.create(name='Food')
        self.products = {}
        for name, price in (('Apple', '2.00'), ('Bread', '4.00'), ('Hammer', '30.00')):
            self.products[name] = Product.objects.create(
                name=name, price=Decimal(price), status='active', category=food,
                available_since=date(2026, 1, 15))
        with open(DEMO_DESIGNS / 'product_grid.json') as stream:
            document = json.load(stream)
        _page, errors = publishing.publish(document)
        self.assertEqual(errors, [])

    def open(self):
        self.go('/designs/product-grid')
        self.wait_js("return document.querySelectorAll(arguments[0] + "
                     "' tbody tr[data-key]').length === 3", TABLE,
                     message='the grid never filled')

    def row(self, name):
        return '%s tr[data-id="%d"]' % (TABLE, self.products[name].pk)

    def has_class(self, name, css_class):
        return self.js('var tr = document.querySelector(arguments[0]);'
                       'return !!tr && tr.classList.contains(arguments[1]);',
                       self.row(name), css_class)

    def cell_text(self, name, column):
        """Read in one go: the grid replaces a row's cells when it redraws."""
        return self.js('var td = document.querySelector(arguments[0]);'
                       'return td ? td.textContent.trim() : null;',
                       '%s td[data-column="%s"]' % (self.row(name), column))

    def edit(self, name, column, value):
        """Click the cell, wait for its widget to be filled, type ``value``."""
        cell = '%s td[data-column="%s"]' % (self.row(name), column)
        self.driver.find_element(By.CSS_SELECTOR, cell).click()
        field = self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, cell + ' input')), 'the cell never became editable')
        self.wait.until(lambda d: field.get_attribute('value'),
                        'the widget was never filled')
        field.clear()
        field.send_keys(value)
        self.wait.until(lambda d: self.has_class(name, 'gtgrid-changed'),
                        'the row was never marked as changed')
        return field

    def save(self):
        self.wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '#product_grid_grid .gtgrid-save'))).click()

    def test_two_rows_are_edited_and_saved_together(self):
        self.open()
        self.edit('Apple', 'name', 'Green apple')
        self.edit('Bread', 'price', '5.25')
        self.assertFalse(self.has_class('Hammer', 'gtgrid-changed'))
        self.save()
        self.wait.until(lambda d: not self.has_class('Apple', 'gtgrid-changed')
                        and not self.has_class('Bread', 'gtgrid-changed'),
                        'the rows were never saved')
        apple = Product.objects.get(pk=self.products['Apple'].pk)
        bread = Product.objects.get(pk=self.products['Bread'].pk)
        self.assertEqual(apple.name, 'Green apple')
        self.assertEqual(bread.price, Decimal('5.25'))
        # Only what changed was written: the other columns kept their values.
        self.assertEqual((apple.price, bread.name, bread.status),
                         (Decimal('2.00'), 'Bread', 'active'))
        self.assertEqual(self.cell_text('Apple', 'name'), 'Green apple')

    def test_a_conflict_marks_its_row_and_it_reloads(self):
        self.open()
        apple_field = self.edit('Apple', 'name', 'Green apple')
        self.edit('Bread', 'name', 'Rye bread')
        # Somebody else saves the bread meanwhile.
        bread = self.products['Bread']
        Product.objects.filter(pk=bread.pk).update(name='Whole bread')

        self.save()
        self.wait.until(lambda d: self.has_class('Bread', 'gtgrid-conflict'),
                        'the conflict was never marked on its row')
        # Nothing was saved, and the other row keeps its change.
        self.assertEqual(Product.objects.get(pk=self.products['Apple'].pk).name,
                         'Apple')
        self.assertEqual(Product.objects.get(pk=bread.pk).name, 'Whole bread')
        self.assertFalse(self.has_class('Apple', 'gtgrid-conflict'))
        self.assertTrue(self.has_class('Apple', 'gtgrid-changed'))
        self.assertEqual(apple_field.get_attribute('value'), 'Green apple')

        self.driver.find_element(
            By.CSS_SELECTOR, self.row('Bread') + ' .gtgrid-reload').click()
        self.wait.until(lambda d: self.cell_text('Bread', 'name') == 'Whole bread',
                        'the row was not reloaded with the current data')
        self.assertFalse(self.has_class('Bread', 'gtgrid-conflict'))
        self.assertTrue(self.has_class('Apple', 'gtgrid-changed'))

        # Saving again writes the other row.
        self.save()
        self.wait.until(lambda d: not self.has_class('Apple', 'gtgrid-changed'),
                        'the second save never finished')
        self.assertEqual(Product.objects.get(pk=self.products['Apple'].pk).name,
                         'Green apple')
        self.assertEqual(Product.objects.get(pk=bread.pk).name, 'Whole bread')
