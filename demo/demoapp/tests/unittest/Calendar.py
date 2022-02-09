from demoapp.calendar.forms import CalendarModelform
from demoapp.models import Event, Calendar
from django.test import TestCase, RequestFactory
from datetime import date, timedelta, datetime
from django import forms
from djgentelella.widgets.calendar import CalendarInput
from django.template import Template, Context


class FormCalendarWidgetTest(TestCase):

    def render(self, msg, context={}):
        template = Template(msg)
        context = Context(context)
        return template.render(context)

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

