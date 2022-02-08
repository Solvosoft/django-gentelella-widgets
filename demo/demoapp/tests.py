from datetime import date, timedelta, datetime
from django import forms
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.forms import forms

from django.template import Template, Context
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.urls import reverse_lazy, path

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from demoapp.calendar.forms import CalendarModelform
from demoapp.models import Event, Calendar
from djgentelella.views.storyline import StorylineBuilder
from djgentelella.views.storymap import BaseStoryMapMBView, BaseStoryMapGPView
from djgentelella.widgets.calendar import CalendarInput
from djgentelella.widgets.storyline import UrlStoryLineInput
from djgentelella.widgets.storymap import MapBasedStoryMapInput, GigaPixelStoryMapInput


# Create your tests here.

class FormCalendarWidgetTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.modelForm = CalendarModelform()
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.event = Event.objects.create(
            calendar=self.calendar,
            title='Event 1',
            start=date.today(),
            end=date.today() + timedelta(minutes=30)
        )

    def test_widget_from_modelform(self):
        events = self.render('{{form.events}}', {'form': self.modelForm})
        self.assertIn('name="events_display"', events)

    def test_JSONField_events(self):
        calendar = Calendar.objects.create(
            title='CalendarTest',
            events={
                'events': self.events,
            }
        )
        calendarWidget = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=calendar.events['events']
            )
        )
        self.assertEquals(calendarWidget.widget.events, self.events)

class CalendarWidgetFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)

    def setUp(self):
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.events = [
            Event(calendar=self.calendar, title='Event 1', start=date.today(),
                  end=date.today() + timedelta(minutes=30)),
            Event(calendar=self.calendar, title='Event 2', start=date.today() + timedelta(days=1),
                  end=date.today() + timedelta(minutes=30)),
            Event(calendar=self.calendar, title='Event 3', start=date.today() + timedelta(days=2),
                  end=date.today() + timedelta(minutes=30))
        ]
        Event.objects.bulk_create(self.events)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()

    def test_events_showing(self):
        self.selenium.get(self.live_server_url + '/calendar_view')
        assert 'Event 1' in self.selenium.page_source
        assert 'Event 2' in self.selenium.page_source
        assert 'Event 3' in self.selenium.page_source

    def test_events_save(self):
        self.selenium.get(self.live_server_url + '/calendar_view')
        self.selenium.find_element(By.ID, 'id_title').send_keys('CalendarTest')
        self.selenium.find_element(By.XPATH, '//button[type="submit"]').click()
        assert self.events == Calendar.objects.last().events


class StoryMapWithSeleniumTestCase(StaticLiveServerTestCase):
    """ Storymaps tests using Selenium"""

    @classmethod
    def setUpClass(cls):
        """ Set up class for Selenium tests """
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)
        super(StoryMapWithSeleniumTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        """ Tear Down class for Selenium tests """
        super(StoryMapWithSeleniumTestCase, cls).tearDownClass()
        cls.selenium.quit()

    def test_display_storymaps(self):
        """ Display both Gigapixel and MapBased storymaps """
        self.selenium.get(self.live_server_url)

        assert 'mapbased_storymap' in self.selenium.page_source
        assert 'gigapixel_storymap' in self.selenium.page_source

    def test_slides_title_data(self):
        """ Test Storymaps main titles from the first slide data """
        self.selenium.get(self.live_server_url)

        response = self.selenium.find_element(By.CSS_SELECTOR, 'body').text
        self.assertTrue('COSTA RICA PLACES TO VISIT' in response)
        self.assertTrue('A Sunday on La Grande Jatte' in response)


class StoryMapFormWidgetTest(TestCase):
    """ Storymaps widgets functionality inside Forms"""

    def setUp(self):
        """ Set up method for the tests """
        class StoryMapFormClass(forms.Form):
            gp_storymap = forms.CharField(widget=GigaPixelStoryMapInput, required=False)
            mb_storymap = forms.CharField(widget=MapBasedStoryMapInput, disabled=True)

        self.form = StoryMapFormClass()

    def render(self, msg, context={}):
        """ Render method for the template """
        template = Template(msg)
        context = Context(context)
        return template.render(context)

    def test_widget_id_form(self):
        """ Test both gigapixel and mapbased storymaps id's inside the form """
        gp_storymap_id = self.render('{{form.gp_storymap.id_for_label}}', {'form': self.form})
        mb_storymap_id = self.render('{{form.mb_storymap.id_for_label}}', {'form': self.form})
        self.assertEqual(gp_storymap_id, 'id_gp_storymap')
        self.assertEqual(mb_storymap_id, 'id_mb_storymap')

    def test_widget_name_form(self):
        """ Test both gigapixel and mapbased storymaps names inside the form """
        gp_storymap_name = self.render('{{form.gp_storymap.html_name}}', {'form': self.form})
        mb_storymap_name = self.render('{{form.mb_storymap.html_name}}', {'form': self.form})
        self.assertEqual(gp_storymap_name, 'gp_storymap')
        self.assertEqual(mb_storymap_name, 'mb_storymap')

    def test_form_field_id(self):
        """ Test form id's widgets related to both of the storymaps types """
        storymap = self.render('{{form}}', {'form': self.form})
        self.assertIn('id="id_gp_storymap"', storymap)
        self.assertIn('id="id_mb_storymap"', storymap)

    def test_form_field_data_widget(self):
        """ Test form data widgets related to both of the storymaps types """
        storymap = self.render('{{form}}', {'form': self.form})
        self.assertIn('data-widget="GigaPixelStoryMapInput"', storymap)
        self.assertIn('data-widget="MapBasedStoryMapInput"', storymap)

    def test_widget_required_false(self):
        """ Test extra attr required field for the gigapixel storymap widget """
        required = self.render('{{form.gp_storymap.required}}', {'form': self.form})
        self.assertFalse(required)

    def test_widget_disabled_true(self):
        """ Test extra attr disabled field for the mapbased storymap widget """
        disabled = self.render('{{form.mb_storymap.disabled}}', {'form': self.form})
        self.assertFalse(disabled)


class MapBasedStoryMapWidgetTestCase(TestCase):
    """ MapBased storymap widget tests """

    def setUp(self):
        """ Set up method for the tests """
        self.factory = RequestFactory()
        self.mapbased_view = BaseStoryMapMBView()
        self.storymap = forms.CharField(widget=MapBasedStoryMapInput(
            attrs={"data-url": reverse_lazy('examplestorymapmb-list')}))

        self.url = reverse('examplestorymapmb-list')

    def test_assert_response_valid_data(self):
        """ Test response valid data from the Gtstorymap example"""
        request = self.factory.get(self.url)
        response = self.mapbased_view.list(request)

        self.assertEqual(response.status_code, 200)


class GigaPixelStoryMapWidgetTestCase(TestCase):
    """ GigaPixel storymap widget tests """

    def setUp(self):
        """ Set up method for the tests """
        self.factory = RequestFactory()
        self.gigapixel_view = BaseStoryMapGPView()

        self.url = reverse('examplestorymapgp-list')

    def get_storymap_options(self):
        return {
            "map_type": "zoomify",
            "map_background_color": "#333",
            "map_as_image": True,
            "calculate_zoom": False,
            "zoomify": {
                "path": "http://cdn.verite.co/maps/zoomify/seurat/",
                "width": 30000,
                "height": 19970,
                "tolerance": 0.9,
                "attribution": "<a href='http://www.google.com/culturalinstitute/asset-viewer/a-sunday-on-la-grande-jatte-1884/twGyqq52R-lYpA?projectId=art-project' target='_blank'>Google Art Project</a>"
            }
        }

    def test_assert_response_valid_data(self):
        """ Test response valid data from the Gtstorymap example"""
        request = self.factory.get(self.url)
        response = self.gigapixel_view.list(request)

        self.assertEqual(response.status_code, 200)


class StorylineWidgetSeleniumTest(StaticLiveServerTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = webdriver.Chrome(executable_path='/home/ricardoalfaro/Descargas/chromedriver')
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def test_widget_assignation(self):
        # Choose your url to visit
        self.selenium.get(self.live_server_url)
        assert 'id_storyline' in self.selenium.page_source

    def test_widget_in_page(self):
        self.selenium.get(self.live_server_url)
        storyline = self.selenium.find_element_by_class_name('storyline-wrapper')
        # deprecated, change to find element(by='class_name', value= "")

        self.assertNotEqual(storyline, None)
        self.assertEqual("/gtapis/storyline/", storyline.get_attribute('data-url'))
        self.assertEqual("storyline-wrapper", storyline.get_attribute('class'))
        self.assertEqual("568", storyline.get_attribute('height'))
        self.assertEqual("1112", storyline.get_attribute('width'))
        self.assertEqual("UrlStoryLineInput", storyline.get_attribute('data-widget'))

