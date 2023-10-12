from datetime import date, timedelta

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.firefox.webdriver import WebDriver

from demoapp.models import Event, Calendar


class CalendarWidgetFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(CalendarWidgetFormSeleniumTest, cls).setUpClass()

        cls.timeout = 10
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(cls.timeout)

    def setUp(self):
        Event.objects.all().delete()
        Calendar.objects.all().delete()
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.events = [
            Event(calendar=self.calendar, title='Event 1', start=date.today(),
                  end=date.today() + timedelta(minutes=30)),
            Event(calendar=self.calendar, title='Event 2',
                  start=date.today() + timedelta(days=1),
                  end=date.today() + timedelta(days=1, minutes=30)),
            Event(calendar=self.calendar, title='Event 3',
                  start=date.today() + timedelta(days=2),
                  end=date.today() + timedelta(days=2, minutes=30))
        ]
        Event.objects.bulk_create(self.events)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(CalendarWidgetFormSeleniumTest, cls).tearDownClass()

    @override_settings(DEBUG=True)
    def test_events_showing(self):
        url = self.live_server_url + str(reverse('calendar_view'))
        self.selenium.get(url)
        elements = self.selenium.find_element(By.CLASS_NAME, "fc-event-title")
        assert 'Event 1' in self.selenium.page_source
        assert 'Event 2' in self.selenium.page_source
        assert 'Event 3' in self.selenium.page_source

    @override_settings(DEBUG=True)
    def test_events_save(self):
        url = self.live_server_url + str(reverse('calendar_view'))
        self.selenium.get(url)
        self.selenium.find_element(By.ID, 'id_title').send_keys('CalendarTest')
        # self.selenium.find_element(By.ID, 'id_options').send_keys('{}')
        element = self.selenium.find_element(By.XPATH, '//input[@type="submit"]')
        self.selenium.execute_script("arguments[0].click();", element)
        self.selenium.implicitly_wait(10)
        assert len(self.events) == len(Calendar.objects.last().events)
