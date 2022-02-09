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

    def build_attrs(self, base_attrs, extra_attrs=None):
        if extra_attrs is not None:
            if 'required' in extra_attrs:
                extra_attrs.pop('required')
        attrs = super(CalendarInput, self).build_attrs(base_attrs, extra_attrs=extra_attrs)
        return attrs

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs=attrs)
        if callable(self.events):
            self.events = self.events()

        if self.events:
            context['events'] = self.events_to_json(self.events)
        else:
            context['events'] = '""'
        context['options'] = self.calendar_attrs
        return context

    def events_to_json(self, events):
        events_serializer = EventSerializer(data=list(events), many=True)
        if events_serializer.is_valid(raise_exception=True):
            return json.dumps(events_serializer.data)
