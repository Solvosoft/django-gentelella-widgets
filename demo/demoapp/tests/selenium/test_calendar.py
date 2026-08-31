"""Browser tests for ``CalendarInput``.

Nothing about a calendar is visible from python: the server ships a JSON list
of events and a block of options, and everything after that is FullCalendar
drawing a month grid. Two kinds of breakage are invisible without a browser --
an option the library no longer understands, and the three CSS overrides in
``gentelella/widgets/calendar.html``, which target FullCalendar's own internal
class names and so depend on a DOM the library is free to change between major
versions.
"""

from django.test import tag
from django.utils import timezone

from demoapp.models import Calendar, Event
from .base import By, SeleniumTestCase

#: The widget names its container after the form field, not after the widget.
CALENDAR = '#id_events'


@tag('selenium')
class CalendarWidgetTest(SeleniumTestCase):

    def setup_data(self):
        # Mid-month, so the event lands in the grid the calendar opens on
        # whatever day the suite runs.
        today = timezone.localtime()
        calendar = Calendar.objects.create(title='Demo', options={}, events=[])
        Event.objects.create(
            calendar=calendar, title='Reunión de equipo',
            start=today.replace(hour=10, minute=0, second=0, microsecond=0),
            end=today.replace(hour=11, minute=0, second=0, microsecond=0),
            color='#26b99a', description='Una descripción para el tooltip')

    def open_calendar(self):
        self.go('/calendar_view')
        self.wait_js(
            "return typeof FullCalendar !== 'undefined'",
            message='FullCalendar never loaded')
        self.wait_js(
            "return document.querySelectorAll('.fc-view-harness').length > 0",
            message='the calendar never rendered')

    def test_the_month_grid_is_drawn(self):
        self.open_calendar()

        # 6 rows of 7 days is what a month view lays out, give or take the
        # short months FullCalendar collapses to 5.
        days = self.js(
            "return document.querySelectorAll('.fc-daygrid-day').length;")
        self.assertGreaterEqual(days, 28, 'the month grid has no day cells')
        self.assertTrue(
            self.js("return document.querySelectorAll('.fc-toolbar').length > 0"),
            'the calendar header toolbar is missing')

    def test_it_carries_no_stylesheet_of_its_own_any_more(self):
        """FullCalendar 6 injects its CSS from javascript.

        If someone re-adds the 5.x ``main.min.css`` link it 404s silently, and
        the grid still looks nearly right -- so assert the styles arrived the
        way they now do.
        """
        self.open_calendar()

        self.assertTrue(self.js(
            "const cell = document.querySelector('.fc-daygrid-day');"
            "return getComputedStyle(cell).borderTopStyle !== 'none';"),
            'FullCalendar did not inject its own styles')

    def test_the_widget_css_overrides_still_reach_the_dom(self):
        """The three rules in calendar.html target FullCalendar internals.

        A major version is free to rename ``fc-daygrid-day-frame``; if it does,
        a busy day silently stops being clipped and warps the whole grid.
        """
        self.open_calendar()

        heights = self.js(
            "const frame = document.querySelector("
            "  arguments[0] + ' .fc-daygrid-day-frame');"
            "const events = document.querySelector("
            "  arguments[0] + ' .fc-daygrid-day-events');"
            "return [frame ? getComputedStyle(frame).height : null,"
            "        events ? getComputedStyle(events).maxHeight : null];",
            CALENDAR)
        self.assertEqual(heights[0], '130px',
                         'the day frame is not being capped any more')
        self.assertEqual(heights[1], '90px',
                         'the day events box is not being capped any more')

    def test_the_events_from_the_server_are_placed(self):
        self.open_calendar()

        titles = self.js(
            "return Array.from(document.querySelectorAll('.fc-event-title'))"
            "  .map(e => e.textContent.trim());")
        self.assertTrue(titles, 'no event was drawn on the calendar')
        # eventDidMount hangs a bootstrap tooltip off the description, which is
        # the one place the widget reaches into FullCalendar's rendering.
        self.assertTrue(self.js(
            "return document.querySelectorAll('.fc-event[data-bs-toggle]')"
            "  .length > 0;"),
            'eventDidMount never ran over the events')

    def test_clicking_an_event_opens_the_detail_modal(self):
        """``eventClick`` reads info.event and its extendedProps."""
        self.open_calendar()

        self.driver.find_element(By.CSS_SELECTOR, '.fc-event').click()

        self.wait_js(
            "return document.querySelectorAll('.modal.show').length > 0;",
            message='clicking an event opened no modal')

    def test_the_page_reports_no_javascript_error(self):
        self.driver.get_log('browser')
        self.open_calendar()

        severe = [entry['message'] for entry in self.driver.get_log('browser')
                  if entry['level'] == 'SEVERE']
        self.assertEqual(severe, [])
