"""The global search box of the top bar (``djgentelella.search``): the demo
turns it on (``GT_SEARCH_NAVBAR``) and its searchable sources are the people
and the countries of ``demoapp/gtdatasources.py``."""
import datetime

from django.test import tag
from django.utils import timezone

from demoapp.models import Country, Person
from .base import EC, By, Keys, SeleniumTestCase

BOX = '.gt-global-search-form input[name="q"]'
HIT = '.gt-global-search-menu .gt-global-search-hit'


@tag('selenium')
class GlobalSearchTest(SeleniumTestCase):

    def setup_data(self):
        self.panama = Country.objects.create(name='Panama', code='pa')
        self.cr = Country.objects.create(name='Costa Rica', code='cr')
        self.ana = Person.objects.create(
            name='Ana Panamá', country=self.cr, born_date=datetime.date(1990, 1, 1),
            last_time=timezone.make_aware(datetime.datetime(2020, 1, 1)))

    def type_in_box(self, text):
        self.go('/')
        box = self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, BOX)))
        box.send_keys(text)
        return box

    def test_autocomplete_opens_a_hit(self):
        self.type_in_box('panam')
        self.wait_js('return document.querySelectorAll(arguments[0]).length >= 2',
                     HIT, message='the box never listed the hits')
        headers = self.js(
            "return Array.from(document.querySelectorAll("
            "'.gt-global-search-menu .dropdown-header'))"
            ".map(h => h.textContent.trim())")
        self.assertEqual(len(headers), 2)
        hit = self.driver.find_element(
            By.XPATH, '//a[contains(@class, "gt-global-search-hit")]'
                      '[div[normalize-space(.)="Panama"]]')
        hit.click()
        self.wait.until(EC.url_contains('/demoapp/country/%s' % self.panama.pk))

    def test_enter_shows_the_results_page_and_opens_a_hit(self):
        box = self.type_in_box('costa')
        box.send_keys(Keys.ENTER)
        self.wait.until(EC.url_contains('/search/?q=costa'))
        groups = self.driver.find_elements(By.CSS_SELECTOR, '.gt-search-group')
        self.assertEqual(sorted(g.get_attribute('data-source') for g in groups),
                         ['demoapp.country', 'demoapp.person'])
        self.driver.find_element(
            By.CSS_SELECTOR, '.gt-search-group[data-source="demoapp.person"] '
                             'a.gt-search-hit').click()
        self.wait.until(EC.url_contains('/demoapp/person/%s' % self.ana.pk))
        self.assertIn('Ana Panamá', self.driver.page_source)

    def test_keyboard_navigation(self):
        box = self.type_in_box('costa')
        self.wait_js('return document.querySelectorAll(arguments[0]).length >= 2',
                     HIT, message='the box never listed the hits')
        box.send_keys(Keys.ARROW_DOWN)
        first = self.js("return document.querySelector(arguments[0] + '.active')"
                        ".getAttribute('href')", HIT)
        box.send_keys(Keys.ENTER)
        self.wait.until(EC.url_contains(first))
