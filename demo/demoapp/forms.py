from django import forms

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets import numberknobinput as knobwidget
from djgentelella.widgets.core import NumberInput
from djgentelella.widgets.selects import AutocompleteSelect
from .models import Foo, Person, Comunity, YesNoInput, ChoiceItem


class FooModelForm(GTForm, forms.ModelForm):
    class Meta:
        model = Foo
        fields = ('number_of_eyes',
                  'speed_in_miles_per_hour',
                  'age')
        widgets = {
            'number_of_eyes': knobwidget.NumberKnobInput(attrs={
                "value": 0
            }),
            'speed_in_miles_per_hour': knobwidget.NumberKnobInput(
                attrs={
                    "value": 1,
                    "data-min": 1,
                    "data-step": 0.1,
                    "data-max": 50
                }),
            'age': knobwidget.NumberKnobInput(attrs={
                "value": 0
            })
        }


class FooBasicForm(GTForm, forms.Form):
    """creates a basic form with three widgets using different attrs"""
    age = forms.IntegerField(
        widget=knobwidget.NumberKnobInput(attrs={}), initial=15)
    speed_in_miles_per_hour = forms.FloatField(
        widget=knobwidget.NumberKnobInput(attrs={
            "data-min": 1,
            "data-step": 0.1,
            "data-max": 50}))
    number_of_eyes = forms.IntegerField(
        widget=knobwidget.NumberKnobInput(attrs={
            "data-min": 1,
            "steps": 0.1,
            "data-max": 50}))


class PersonForm(GTForm, forms.ModelForm):
    class Meta:
        model = Person
        fields = '__all__'
        widgets = {
            'country': AutocompleteSelect('countrybasename'),
            'last_time': genwidgets.DateInput,
            'born_date': genwidgets.DateInput,
            'name': genwidgets.TextInput,
            'num_children': NumberInput,

        }


class PersonModalForm(GTForm, forms.ModelForm):
    test_a = forms.ChoiceField(
        choices=[(1, 'one'), (2, 'two'), (3, 'three'), (4, 'four')],
        widget=genwidgets.SelectMultiple(
            attrs={'data-dropdownparent': '#exampleModal'}))

    class Meta:
        model = Person
        fields = ['country', 'num_children']
        widgets = {
            'country': AutocompleteSelect(
                'countrybasename',
                attrs={'data-dropdownparent': '#exampleModal',
                       'data-placeholder': 'Custom placeholder'}),
            'num_children': genwidgets.Select(choices=[(1, 'one'),
                                                       (2, 'two'),
                                                       (3, 'three'),
                                                       (4, 'four')], attrs={
                'data-dropdownparent': '#exampleModal'}),

        }


class CityForm(GTForm, forms.ModelForm):
    class Meta:
        model = Comunity
        fields = '__all__'
        widgets = {
            'name': genwidgets.TextInput
        }

class ItemsForm(GTForm, forms.ModelForm):
    class Meta:
        model = ChoiceItem
        fields = '__all__'
        widgets = {
            'name': genwidgets.TextInput
        }

class YesNoInputAddForm(GTForm, forms.ModelForm):
    has_copies = forms.BooleanField(widget=genwidgets.YesNoInput(
        attrs={'rel': ['copy_number']}))
    has_meta = forms.BooleanField(widget=genwidgets.YesNoInput(
        attrs={'rel': ['#id_year', 'editorial']}))
    display_publish = forms.BooleanField(widget=genwidgets.YesNoInput(
        attrs={'rel': ['#display_publish_info']}, shparent='.x_panel'))

    class Meta:
        model = YesNoInput
        fields = '__all__'
        widgets = {
            'name': genwidgets.TextInput,
            'is_public': genwidgets.YesNoInput,
            'copy_number': genwidgets.NumberInput,
            'year': genwidgets.NumberInput,
            'editorial': genwidgets.TextInput
        }
