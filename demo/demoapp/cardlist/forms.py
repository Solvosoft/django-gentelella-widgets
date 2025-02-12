from django import forms

from demoapp.models import Person
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.selects import AutocompleteSelect


class CardListPerson(GTForm, forms.ModelForm):
    default_render_type = 'as_inline'

    class Meta:
        model = Person
        fields = ['name', 'num_children', 'country']
        widgets = {
            'name': genwidgets.TextInput,
            'num_children': genwidgets.NumberInput,
            'country': AutocompleteSelect('countrybasename')
        }
