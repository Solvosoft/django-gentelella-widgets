"""The region components (``cards``, ``calendar``, ``map``) in a browser: the
demo page ``demoapp/gtdesign/meetups.json`` over the ``demoapp.meetups`` data
source. A card opened through its row link, a facet that filters the three,
the calendar moved to the next month and an event opened, and the popup of a
point of the map."""
import json
from datetime import timedelta

from django.test import tag
from django.utils import timezone

from demoapp.models import Meetup
from djgentelella.designs import engine, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import EC, By, SeleniumTestCase

CARDS = '[data-gtdesign="meetup_cards"]'
CALENDAR = '[data-gtdesign="meetup_calendar"]'
MAP = '[data-gtdesign="meetup_map"]'


@tag('selenium')
class RegionComponentsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        with open(DEMO_DESIGNS / 'meetups.json') as stream:
            _page, errors = publishing.publish(json.load(stream))
        self.assertEqual(errors, [])
        # Midday, so a time zone never pushes them to another day or month.
        today = timezone.localtime().replace(hour=12, minute=0, second=0,
                                             microsecond=0)
        self.talk = Meetup.objects.create(
            title='Volcano talk', kind='talk', city='Cartago', starts_at=today,
            location='9.864400,-83.919400')
        self.workshop = Meetup.objects.create(
            title='Leaflet workshop', kind='workshop', city='Madrid',
            starts_at=today + timedelta(days=1), location='40.416800,-3.703800')
        # Next month, whatever the day of the month today is.
        self.later = Meetup.objects.create(
            title='Next month social', kind='social', city='Heredia',
            starts_at=(today.replace(day=1) + timedelta(days=40)).replace(day=20),
            location='9.998100,-84.119700')

    def open_page(self):
        self.go('/designs/meetups/')

    def texts(self, css):
        return self.js('return Array.prototype.map.call('
                       '  document.querySelectorAll(arguments[0]),'
                       '  function (e) { return e.textContent.trim(); });', css)

    def wait_cards(self, predicate, message):
        self.wait.until(lambda d: predicate(sorted(self.texts(
            CARDS + ' .gtcard .card-title'))), message)

    def test_a_card_opens_its_row_link(self):
        self.open_page()
        expected = ['Leaflet workshop', 'Next month social', 'Volcano talk']
        self.wait_cards(lambda titles: titles == expected, 'the cards never loaded')
        link = self.driver.find_element(
            By.XPATH, '//div[@data-gtdesign="meetup_cards"]//a[@class="gtcard-link" '
                      'and normalize-space(.)="Volcano talk"]')
        link.click()
        self.wait.until(EC.url_contains('/admin/demoapp/meetup/%d/change/'
                                        % self.talk.pk))

    def test_a_facet_filters_the_three(self):
        self.open_page()
        self.wait_cards(lambda titles: len(titles) == 3, 'the cards never loaded')
        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 2",
                     message='the facets never rendered')
        self.wait_js("return document.querySelector(arguments[0] + ' .gtmap')"
                     "  .dataset.loaded >= 1", MAP, message='the map never loaded')
        self.mouse_click(self.driver.find_element(
            By.XPATH, '//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                      '"kind"]//label[starts-with(normalize-space(.), "Workshop")]'))
        self.wait_cards(lambda titles: titles == ['Leaflet workshop'],
                        'the cards did not follow the facet')
        self.wait.until(lambda d: self.texts(CALENDAR + ' .fc-event-title')
                        == ['Leaflet workshop'] or self.texts(
                            CALENDAR + ' .fc-event-title') == [],
                        'the calendar did not follow the facet')
        self.assertNotIn('Volcano talk', self.texts(CALENDAR + ' .fc-event-title'))
        self.wait_js("return document.querySelectorAll("
                     "  arguments[0] + ' .leaflet-marker-icon').length === 1", MAP,
                     message='the map did not follow the facet')

    def test_the_calendar_moves_and_opens_an_event(self):
        self.open_page()
        self.wait.until(lambda d: 'Volcano talk' in self.texts(
            CALENDAR + ' .fc-event-title'), 'the events never loaded')
        self.assertNotIn('Next month social',
                         self.texts(CALENDAR + ' .fc-event-title'))
        loads = int(self.js("return document.querySelector("
                            "  arguments[0] + ' .gtcalendar').dataset.loaded",
                            CALENDAR))
        self.driver.find_element(By.CSS_SELECTOR,
                                 CALENDAR + ' .fc-next-button').click()
        # Another request, for the range of the next month only.
        self.wait_js("return Number(document.querySelector(arguments[0] + "
                     "  ' .gtcalendar').dataset.loaded) > arguments[1]",
                     CALENDAR, loads, message='the next month was not asked for')
        self.wait.until(lambda d: 'Next month social' in self.texts(
            CALENDAR + ' .fc-event-title'), 'the next month has not its event')
        event = self.driver.find_element(
            By.XPATH, '//div[@data-gtdesign="meetup_calendar"]//*[contains(@class, '
                      '"fc-event-title") and normalize-space(.)="Next month social"]')
        event.click()
        self.wait.until(EC.url_contains('/admin/demoapp/meetup/%d/change/'
                                        % self.later.pk))

    def test_a_point_opens_its_popup(self):
        self.open_page()
        self.wait_js("return document.querySelectorAll("
                     "  arguments[0] + ' .leaflet-marker-icon').length >= 2", MAP,
                     message='the points never loaded')
        # The one alone in Europe: never in a cluster with the others.
        icon = self.js(
            'var engine = document.querySelector(arguments[0]).gtregion;'
            'var found = null;'
            'Object.keys(engine.layers).forEach(function (name) {'
            '  engine.layers[name].group.eachLayer(function (layer) {'
            '    if (layer.getLatLng && layer.getLatLng().lat > 30) { found = layer; }'
            '  });'
            '});'
            'return found && found._icon;', MAP)
        self.assertIsNotNone(icon)
        icon.click()
        self.wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, MAP + ' .leaflet-popup-content')))
        popup = self.driver.find_element(By.CSS_SELECTOR,
                                         MAP + ' .leaflet-popup-content')
        text = popup.get_attribute('textContent')
        self.assertIn('Leaflet workshop', text)
        self.assertIn('Madrid', text)
        link = popup.find_element(By.CSS_SELECTOR, 'a.gtmap-popup-link')
        self.assertTrue(link.get_attribute('href').endswith(
            '/admin/demoapp/meetup/%d/change/' % self.workshop.pk))
