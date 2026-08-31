import json

from .core import TextInput, update_kwargs
from ..serializers.calendar import EventSerializer


class CalendarInput(TextInput):
    """
    Text input backed by a FullCalendar month view.

    ``events``/``calendar_attrs`` alone render a read-only calendar. Set
    ``add_url``/``update_url``/``delete_url`` to also let the user manage
    events by clicking the calendar -- each is independent, so e.g. add
    without delete is fine. All three POST the same ``X-CSRFToken`` header
    pattern as the rest of the library's AJAX widgets:

    - ``add_url``: clicking an empty day opens a title/color modal and POSTs
      ``title``, ``start``, ``color``. Your view creates the event and
      answers with an object FullCalendar understands, e.g. ``{"id": ...,
      "title": ..., "start": ..., "color": ...}``; it gets added to the
      calendar without a reload.
    - ``update_url``/``delete_url``: clicking an existing event opens the
      same modal pre-filled, editable when ``update_url`` is set. Save POSTs
      ``id``, ``title``, ``color``; a Delete button (only rendered when
      ``delete_url`` is set) POSTs ``id``. Both apply directly to the
      calendar's in-memory event, no reload either.

    Without any of the three the detail popover still works, just read-only.

    :param events: list of FullCalendar event dicts, or a zero-arg callable
                   returning one (evaluated at render time)
    :param calendar_attrs: extra options merged into the FullCalendar
                           ``Calendar`` constructor (view, locale, etc.)
    :param add_url: URL to POST new events to.
    :param update_url: URL to POST an edited event's ``id``/``title``/
                       ``color`` to.
    :param delete_url: URL to POST an event's ``id`` to for deletion.
    """

    template_name = 'gentelella/widgets/calendar.html'

    def __init__(
        self,
        attrs=None,
        calendar_attrs=None,
        events=None,
        add_url=None,
        update_url=None,
        delete_url=None,
    ):
        self.events = events
        self.calendar_attrs = calendar_attrs
        self.add_url = add_url
        self.update_url = update_url
        self.delete_url = delete_url
        attrs = update_kwargs(attrs, self.__class__.__name__, '')
        # `is not None`, not truthiness: these are commonly reverse_lazy()
        # proxies, and forcing one here -- widgets are instantiated in Meta at
        # class-body/import time -- resolves it before urls.py has finished
        # building its own patterns, which is a circular import.
        if add_url is not None:
            attrs['data-add-url'] = add_url
        if update_url is not None:
            attrs['data-update-url'] = update_url
        if delete_url is not None:
            attrs['data-delete-url'] = delete_url
        super(CalendarInput, self).__init__(attrs=attrs, extraskwargs=False)

    def build_attrs(self, base_attrs, extra_attrs=None):
        if extra_attrs is not None:
            if 'required' in extra_attrs:
                extra_attrs.pop('required')
        attrs = super(CalendarInput, self).build_attrs(
            base_attrs, extra_attrs=extra_attrs
        )
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
        # Template-side flags: the data-*-url attrs on the element are for
        # the JS, but {% if widget.attrs.data-add-url %} cannot parse a
        # hyphenated attr name (Django templates read it as subtraction),
        # same reason MapPointInput passes its own flags through context
        # instead.
        context['can_add'] = bool(self.add_url)
        context['can_edit'] = bool(self.update_url)
        context['can_delete'] = bool(self.delete_url)
        return context

    def events_to_json(self, events):
        events_serializer = EventSerializer(data=list(events), many=True)
        if events_serializer.is_valid(raise_exception=True):
            return json.dumps(events_serializer.data)
