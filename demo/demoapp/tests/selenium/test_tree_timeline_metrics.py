"""The ``tree``, ``timeline`` and ``metrics`` region components in a browser:
the demo page ``demoapp/gtdesign/insights.json``. A node of the tree opened
two levels down, the timeline paged backwards, and a metric card that
changes when a facet is applied."""
import json
from datetime import timedelta

from django.test import tag
from django.utils import timezone

from demoapp.models import Department, Meetup
from djgentelella.designs import engine, publishing
from djgentelella.tests.DesignsData_Test import DEMO_DESIGNS

from .base import By, SeleniumTestCase

TREE = '[data-gtdesign="org_tree"]'
TIMELINE = '[data-gtdesign="meetup_timeline"]'
METRICS = '[data-gtdesign="meetup_metrics"]'


@tag('selenium')
class TreeTimelineMetricsTest(SeleniumTestCase):

    def setup_data(self):
        engine.clear_cache()
        with open(DEMO_DESIGNS / 'insights.json') as stream:
            _page, errors = publishing.publish(json.load(stream))
        self.assertEqual(errors, [])
        board = Department.objects.create(name='Board', icon='fa fa-institution')
        operations = Department.objects.create(name='Operations', parent=board)
        Department.objects.create(name='Logistics', parent=operations)
        Department.objects.create(name='Technology', parent=board)
        # This month: two talks and a workshop (midday, so no time zone moves
        # them to another day); four more months ago.
        today = timezone.localtime().replace(hour=12, minute=0, second=0,
                                             microsecond=0)
        for title, kind in (('Volcano talk', 'talk'), ('Coffee talk', 'talk'),
                            ('Leaflet workshop', 'workshop')):
            Meetup.objects.create(title=title, kind=kind, city='Cartago',
                                  starts_at=today)
        for index in range(4):
            Meetup.objects.create(title='Old meetup %d' % index, kind='social',
                                  city='Heredia',
                                  starts_at=today - timedelta(days=70 + index))

    def texts(self, css):
        return self.js('return Array.prototype.map.call('
                       '  document.querySelectorAll(arguments[0]),'
                       '  function (e) { return e.textContent.trim(); });', css)

    def click(self, element):
        """A real click, once ``element`` is in the middle of the screen, on
        top and still: the tree is under the fold, and the timeline and the
        facets above it grow while they load."""
        last = {}

        def ready(_driver):
            self.js('arguments[0].scrollIntoView({block: "center"});', element)
            state = self.element_state(element)
            still = state['topmost'] and state['top'] == last.get('top')
            last['top'] = state['top']
            return still

        self.wait.until(ready, 'the element never stood still on top')
        element.click()

    def toggle(self, title):
        return self.driver.find_element(
            By.XPATH, '//div[@data-gtdesign="org_tree"]//li[@role="treeitem"]'
                      '[./div/*[contains(@class, "gttree-title") and '
                      'normalize-space(.)="%s"]]/div/button' % title)

    def test_a_tree_node_opens(self):
        self.go('/designs/insights/')
        self.wait.until(lambda d: self.texts(TREE + ' .gttree-title') == ['Board'],
                        'the roots never loaded')
        self.click(self.toggle('Board'))
        self.wait.until(lambda d: self.texts(TREE + ' .gttree-title')
                        == ['Board', 'Operations', 'Technology'],
                        'the children of Board never loaded')
        self.assertEqual(self.js(
            "return document.querySelector(arguments[0] + "
            "  ' li[role=treeitem]').getAttribute('aria-expanded')", TREE), 'true')
        # A leaf cannot be opened; a node with children can, one more level.
        self.assertFalse(self.toggle('Technology').is_enabled())
        self.click(self.toggle('Operations'))
        self.wait.until(lambda d: 'Logistics' in self.texts(TREE + ' .gttree-title'),
                        'the children of Operations never loaded')
        # Closing hides them without asking again.
        self.click(self.toggle('Board'))
        self.wait_js("return document.querySelector(arguments[0] + "
                     "  ' li[role=treeitem] > ul').hidden", TREE,
                     message='Board did not close')

    def test_the_timeline_pages_backwards(self):
        self.go('/designs/insights/')
        self.wait.until(lambda d: len(self.texts(TIMELINE + ' .gttimeline-title'))
                        == 5, 'the first page never loaded')
        titles = self.texts(TIMELINE + ' .gttimeline-title')
        self.assertEqual(titles[3:], ['Old meetup 0', 'Old meetup 1'])
        more = self.driver.find_element(By.CSS_SELECTOR, TIMELINE + ' .gttimeline-more')
        self.assertTrue(more.is_displayed())
        self.click(more)
        self.wait.until(lambda d: len(self.texts(TIMELINE + ' .gttimeline-title'))
                        == 7, 'the older page never loaded')
        self.assertEqual(self.texts(TIMELINE + ' .gttimeline-title')[5:],
                         ['Old meetup 2', 'Old meetup 3'])
        self.wait_js("return document.querySelector(arguments[0] + "
                     "  ' .gttimeline-more').classList.contains('d-none')", TIMELINE,
                     message='"Load older" is still there after the last page')

    def card_value(self, label):
        return self.js(
            "var found = null, wanted = arguments[1];"
            "document.querySelectorAll(arguments[0] + ' .gtmetric').forEach("
            "  function (card) {"
            "    if (card.querySelector('.gtmetric-label').textContent.trim()"
            "        .indexOf(wanted) === 0) {"
            "      found = card.querySelector('.gtmetric-value').textContent.trim();"
            "    }"
            "  });"
            "return found;", METRICS, label)

    def test_a_metric_card_follows_a_facet(self):
        self.go('/designs/insights/')
        self.assertEqual(self.card_value('Meetups'), '3')
        self.assertEqual(self.card_value('Workshops'), '1')
        self.wait_js("return document.querySelectorAll("
                     "  '.gtdesign-facets .gt-facet').length === 2",
                     message='the facets never rendered')
        label = self.driver.find_element(
            By.XPATH, '//div[contains(@class, "gtdesign-facets")]//div[@data-column='
                      '"kind"]//label[starts-with(normalize-space(.), "Workshop")]')
        self.click(label)
        self.wait.until(lambda d: self.card_value('Meetups') == '1',
                        'the metric card did not follow the facet')
        self.assertEqual(self.card_value('Cities'), '1')
        self.wait.until(lambda d: self.texts(TIMELINE + ' .gttimeline-title')
                        == ['Leaflet workshop'], 'the timeline did not follow')
