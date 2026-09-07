from django import forms

from demoapp.models import Person
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.selects import AutocompleteSelect


class CardListPerson(GTForm, forms.ModelForm):
    default_render_type = 'as_inline'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields:
            self.fields[f].required = False

    class Meta:
        model = Person
        fields = ['name', 'num_children', 'country']
        widgets = {
            'name': genwidgets.TextInput,
            'num_children': genwidgets.NumberInput,
            'country': AutocompleteSelect('countrybasename')
        }


class CardListPersonForm(GTForm, forms.ModelForm):
    """Add/edit form for the create and update modals of the card list demo.

    A separate form from ``CardListPerson``: that one is the filter bar, which
    only exposes the three fields worth filtering by. Creating or editing a
    Person needs every required model field, ``born_date`` and ``last_time``
    included, or the API rejects the submission as incomplete.
    """

    class Meta:
        model = Person
        fields = ['name', 'num_children', 'country', 'born_date', 'last_time']
        widgets = {
            'name': genwidgets.TextInput,
            'num_children': genwidgets.NumberInput,
            'country': AutocompleteSelect('countrybasename'),
            'born_date': genwidgets.DateInput,
            'last_time': genwidgets.DateTimeInput,
        }
