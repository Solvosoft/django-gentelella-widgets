import json

from django.db.models import QuerySet
from django.utils.safestring import mark_safe
from .core import TextInput, update_kwargs
from ..serializers.calendar import EventSerializer


class CalendarInput(TextInput):
    template_name = 'gentelella/widgets/calendar.html'

    def __init__(self, attrs=None, calendar_attrs=None, events=None):
        self.events = events
        self.calendar_attrs = calendar_attrs
        attrs = update_kwargs(attrs, self.__class__.__name__, "")
        super(CalendarInput, self).__init__(attrs=attrs, extraskwargs=False)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs=attrs)
        context['events'] = self.events_to_json(self.events)
        context['options'] = self.calendar_attrs
        return context

    def events_to_json(self, events):
        events_serializer = EventSerializer(data=list(events), many=True)
        if events_serializer.is_valid(raise_exception=True):
            return json.dumps(events_serializer.data)
