from ..models import Event, Calendar
from djgentelella.forms.forms import GTForm
from django import forms
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.calendar import CalendarInput


class CalendarForm(GTForm, forms.Form):
    calendar = forms.CharField(
        widget=CalendarInput(
            calendar_attrs={},
            events=Event.objects.all().values('title', 'start', 'end')
        )
    )


def get_events():
    return Event.objects.all().values('title', 'start', 'end')

class CalendarModelform(GTForm, forms.ModelForm):
    class Meta:
        model = Calendar
        fields = '__all__'
        widgets = {
            'title': genwidgets.TextInput,
            'options': genwidgets.Textarea,
            'events': CalendarInput(
                calendar_attrs={},
                events=get_events
            ),
        }