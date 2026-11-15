"""What the demo flows call besides the built-in actions."""

from datetime import datetime, time

from django.utils import timezone

from demoapp.models import Calendar, Event


def add_to_calendar(context):
    """An approved leave shows in the demo calendar.

    Declared ``on_commit``: it stands for an external system (a shared
    calendar) that a rolled back transition must never reach.
    """
    leave = context.obj
    calendar, _created = Calendar.objects.get_or_create(title='Demo')
    zone = timezone.get_current_timezone()
    Event.objects.create(
        calendar=calendar, title='Vacaciones: %s' % leave.employee,
        start=datetime.combine(leave.start, time(8), zone),
        end=datetime.combine(leave.end, time(17), zone),
        color='#2ecc71', description=leave.reason)
