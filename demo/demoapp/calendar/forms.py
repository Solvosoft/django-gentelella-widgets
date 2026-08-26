from django import forms
from django.urls import reverse_lazy

from djgentelella.forms.forms import GTForm
from djgentelella.widgets.calendar import CalendarInput
from ..models import Event, Calendar


class CalendarForm(GTForm, forms.Form):
    calendar = forms.CharField(
        widget=CalendarInput(
            calendar_attrs={},
            events=Event.objects.all().values('title', 'start', 'end')
        )
    )


def get_events():
    # EventSerializer's fields are required=False but not allow_null=True, so
    # an explicit {'end': None} from a .values() row nobody set one on fails
    # validation -- every one of title/start/end/color is nullable on the
    # model, so drop whichever key came back None instead of sending it.
    # `id` has to travel too: without it FullCalendar makes up its own for
    # events loaded at render time, and the edit/delete modal's POST -- keyed
    # on the real Event pk -- 404s against that instead.
    # description isn't a field EventSerializer knows about (unlike the AJAX
    # create/update responses, which skip that serializer and let
    # FullCalendar bucket any non-core key into extendedProps on its own) --
    # here it has to be nested under extendedProps itself or validation
    # rejects the whole event for the unrecognized key.
    events = []
    for event in Event.objects.all().values(
            'id', 'title', 'start', 'end', 'color', 'description'):
        event['id'] = str(event['id'])
        description = event.pop('description', None)
        event = {k: v for k, v in event.items() if v is not None}
        if description:
            event['extendedProps'] = {'description': description}
        events.append(event)
    return events


class CalendarModelform(GTForm, forms.ModelForm):
    class Meta:
        model = Calendar
        # title/options exist on the model but nothing reads them back --
        # calendar_attrs below is hardcoded, and title is only ever set to
        # the fixed 'Demo' string in views.py's get_or_create. Rendering them
        # let you edit values that go straight into a black hole.
        fields = ['events']
        widgets = {
            'events': CalendarInput(
                calendar_attrs={},
                events=get_events,
                add_url=reverse_lazy('calendar-event-create'),
                update_url=reverse_lazy('calendar-event-update'),
                delete_url=reverse_lazy('calendar-event-delete'),
            ),
        }
