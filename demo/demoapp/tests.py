import json
import time
from datetime import date, timedelta, datetime

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.forms import formset_factory
from django.template import Template, Context
from rest_framework import serializers

from django import forms
from django.test import TestCase, RequestFactory
from django.db import models

# Create your tests here.
from selenium.webdriver.common.by import By

from selenium.webdriver.firefox.webdriver import WebDriver

from demoapp.forms import CalendarForm, CalendarModelform
from demoapp.models import Event, Calendar
from djgentelella.forms.forms import GTForm
from djgentelella.serializers.calendar import EventSerializer
from djgentelella.widgets.calendar import CalendarInput


class CalendarWidgetTest(TestCase):

    def setUp(self):
        self.events = [
            {
                'title': 'Event 1',
                'start': datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(minutes=30), "%Y-%m-%d %H:%M:%S.%f")
            },
            {
                'title': 'Event 2',
                'start': datetime.strftime(datetime.now() + timedelta(days=1), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(days=1, minutes=30), "%Y-%m-%d %H:%M:%S.%f")
            },
            {
                'title': 'Event 3',
                'start': datetime.strftime(datetime.now() + timedelta(days=2), "%Y-%m-%d %H:%M:%S.%f"),
                'end': datetime.strftime(datetime.now() + timedelta(days=2, minutes=30), "%Y-%m-%d %H:%M:%S.%f")
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

    def test_wrong_field_names(self):
        wrong_fields_event = [
            {
                'name': 'Event 4',
                'startDate': datetime.now(),
                'endDate': datetime.now() + timedelta(days=1)
            }
        ]
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=wrong_fields_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Serializer data is not accepted."):
            calendar.widget.events_to_json(calendar.widget.events)

    def test_past_end_date(self):
        wrong_date_event = [
            {
                'title': 'Event 4',
                'start': datetime.now() + timedelta(days=1),
                'end': datetime.now()
            }
        ]
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=wrong_date_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Event end date must occur after start date"):
            calendar.widget.events_to_json(calendar.widget.events)

    def test_empty_events(self):
        empty_event = {}
        calendar = forms.CharField(
            widget=CalendarInput(
                calendar_attrs={},
                events=empty_event
            )
        )
        with self.assertRaisesMessage(serializers.ValidationError, "Empty event parameter."):
            calendar.widget.events_to_json(calendar.widget.events)

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

class FormCalendarWidgetTest(TestCase):

    def setUp(self):
        self.calendar = Calendar.objects.create(title='Calendar 1', options={})
        self.events = Event.objects.create(
            calendar=self.calendar,
            title='Event 1',
            start=date.today(),
            end=date.today() + timedelta(minutes=30)
        )
        self.factory = RequestFactory()
        self.form = CalendarForm()
        self.modelForm = CalendarModelform()

    def render(self, msg, context={}):
        template = Template(msg)
        context = Context(context)
        return template.render(context)

    def test_widget_id_form(self):
        calendar_id = self.render('{{form.calendar.id_for_label}}', {'form': self.form})
        self.assertEquals(calendar_id, 'id_calendar')

    def test_events_src_input(self):
        calendar_name = self.render('{{form.calendar.html_name}}', {'form': self.form})
        self.assertEquals(calendar_name, 'calendar')

    def test_widget_name_form(self):
        calendar_input = self.render('{{form}}', {'form': self.form})
        self.assertIn('name="calendar_display"', calendar_input)

    def test_widget_not_required(self):
        self.form.fields['calendar'].required = True
        calendar_required = self.render('{{form.calendar.required}}', {'form': self.form})
        self.assertFalse(calendar_required)

    def test_widget_formset(self):
        CalendarFormSet = formset_factory(CalendarForm, extra=2)
        formset = CalendarFormSet()
        for formIndex in range(len(formset)):
            calendar_name = self.render('{{form}}', {'form': formset[formIndex]})
            self.assertIn(f'name="form-{formIndex}-calendar_display"', calendar_name)


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
        assert self.events in Calendar.objects.last().events

