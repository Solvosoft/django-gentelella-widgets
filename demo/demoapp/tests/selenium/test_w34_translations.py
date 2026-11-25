"""W34 in the browser: switching the language shows the menu and a design
page -- its title, a stat, a table title and a column header -- in that
language, from translations stored as data."""
from pathlib import Path

from django.core.management import call_command
from django.test import tag

from demoapp import models
from djgentelella.models import MenuItem

from .base import By, EC, SeleniumTestCase

DESIGN = Path(models.__file__).resolve().parent / 'gtdesign' / 'translated.json'


@tag('selenium')
class MetadataTranslationsTest(SeleniumTestCase):

    def setup_data(self):
        food = models.ProductCategory.objects.create(name='Food')
        models.Product.objects.create(name='Apple', price='2.00', status='active',
                                      category=food)
        call_command('gtdesigns_publish', str(DESIGN), verbosity=0)
        MenuItem.objects.create(
            title='Catálogo traducido', translations={'en': 'Translated catalogue'},
            url_name='gt-design-page', category='sidebar', is_reversed=True,
            reversed_args='translated', icon='fa fa-language')
        MenuItem.objects.create(
            title='Language', url_name='demoapp.menu_widgets.LanguageMenu',
            category='main', is_widget=True)

    def sidebar_text(self):
        return self.js("return document.querySelector('#sidebar-menu, .left_col')"
                       ".textContent;")

    def column_titles(self):
        return self.js("return Array.from(document.querySelectorAll("
                       "'[data-gtdesign=catalogue] thead th')).map("
                       "function (th) { return th.innerText.trim(); });")

    def wait_column(self, title):
        self.wait_js("var title = arguments[0];"
                     "return Array.from(document.querySelectorAll("
                     "'[data-gtdesign=catalogue] thead th')).some("
                     "function (th) { return th.innerText.trim() === title; });",
                     title, message='no column %r: %r' % (title, self.column_titles()))

    def test_switch_the_language(self):
        self.go('/designs/translated/')
        self.assertIn('Catálogo traducido', self.sidebar_text())
        self.assertIn('Catálogo traducido', self.driver.title)
        self.assertIn('Catálogo de productos', self.js(
            "return document.querySelector('[data-gtdesign=catalogue]').innerText;"))
        self.wait_column('Nombre del producto')
        # The switcher of the top bar: English.
        self.mouse_click('.gt-language-menu button[value=en]')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.gt-language-menu button[value=en].btn-primary')))
        self.wait_js("return document.readyState === 'complete' "
                     "&& typeof jQuery !== 'undefined' && jQuery.isReady")
        self.assertIn('/designs/translated/', self.driver.current_url)
        sidebar = self.sidebar_text()
        self.assertIn('Translated catalogue', sidebar)
        self.assertNotIn('Catálogo traducido', sidebar)
        self.assertIn('Translated catalogue', self.driver.title)
        table = self.js(
            "return document.querySelector('[data-gtdesign=catalogue]').innerText;")
        self.assertIn('Product catalogue', table)
        self.wait_column('Product name')
        self.assertIn('Products', self.js(
            "return document.querySelector('[data-gtdesign=count]').innerText;"))
        # And back.
        self.mouse_click('.gt-language-menu button[value=es]')
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, '.gt-language-menu button[value=es].btn-primary')))
        self.assertIn('Catálogo traducido', self.sidebar_text())
