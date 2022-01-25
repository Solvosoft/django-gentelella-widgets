from datetime import date, timedelta

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver

from django import forms
from django.test import TestCase, LiveServerTestCase

# Create your tests here.
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.webdriver import WebDriver

from demoapp.models import Event, Calendar
from djgentelella.widgets.calendar import CalendarInput


class CalendarWidgetTest(TestCase):

    def setUp(self):

        self.events = [
            {
                'title': 'Event 1',
                'start': date.today(),
                'end': date.today() + timedelta(minutes=30)
            },
            {
                'title': 'Event 2',
                'start': date.today() + timedelta(days=1),
                'end': date.today() + timedelta(days=1, minutes=30)
            },
            {
                'title': 'Event 3',
                'start': date.today() + timedelta(days=2),
                'end': date.today() + timedelta(days=2, minutes=30)
            },
        ]

        self.calendarWidget = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={
                    'initialView': 'timeGridWeek',
                },
                events=self.events
            )
        )

    def test_widget_events(self):
        self.assertEquals(self.calendarWidget.widget.events, self.events)

    def test_calendar_attrs(self):
        self.assertDictEqual(self.calendarWidget.widget.calendar_attrs, {'initialView': 'timeGridWeek'})


class CalendarWidgetFormSeleniumTest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.selenium = WebDriver()
        cls.selenium.implicitly_wait(10)

    def setUp(self):
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.events = [
                Event(calendar=self.calendar, title='Event 1', start=date.today(), end=date.today() + timedelta(minutes=30)),
                Event(calendar=self.calendar, title='Event 2', start=date.today() + timedelta(days=1), end=date.today() + timedelta(minutes=30)),
                Event(calendar=self.calendar, title='Event 3', start=date.today() + timedelta(days=2), end=date.today() + timedelta(minutes=30))
        ]
        Event.objects.bulk_create(self.events)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()

    def test_events_showing(self):
        self.selenium.get(self.live_server_url)
        assert 'Event 1' in self.selenium.page_source
        assert 'Event 2' in self.selenium.page_source
        assert 'Event 3' in self.selenium.page_source
        # xpath


