from django import forms

from demoapp import models
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets.core import TextInput
from djgentelella.widgets.selects import AutocompleteSelect, AutocompleteSelectMultiple


class PeopleGroupForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.PeopleGroup
        fields = '__all__'
        widgets = {
            'name': TextInput,
            'people': AutocompleteSelectMultiple("personbasename",
                                                 attrs={
                                                     'data-s2filter-myinput': '#id_name'}),
            'comunities': AutocompleteSelectMultiple("comunitybasename"),
            'country': AutocompleteSelect('countrybasename')
        }


class ABCDEGroupForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.ABCDE
        fields = '__all__'
        widgets = {
            'a': AutocompleteSelectMultiple("a", attrs={
                'data-related': 'true',
                'data-pos': 0,
                'data-groupname': 'myabcde'
            }),
            'b': AutocompleteSelect("b", attrs={
                'data-related': 'true',
                'data-pos': 1,
                'data-groupname': 'myabcde'
            }),
            'c': AutocompleteSelectMultiple("c", attrs={
                'data-related': 'true',
                'data-pos': 2,
                'data-groupname': 'myabcde'
            }),
            'd': AutocompleteSelect('d', attrs={
                'data-related': 'true',
                'data-pos': 3,
                'data-groupname': 'myabcde'
            }),
            'e': AutocompleteSelectMultiple('e', attrs={
                'data-related': 'true',
                'data-pos': 4,
                'data-groupname': 'myabcde'
            }),
        }


class ABCDEModalGroupForm(CustomForm, forms.ModelForm):
    class Meta:
        model = models.ABCDE
        fields = '__all__'
        widgets = {
            'a': AutocompleteSelectMultiple("a", attrs={
                'data-dropdownparent': '#exampleModal',
                'data-related': 'true',
                'data-pos': 0,
                'data-groupname': 'myabcde'
            }),
            'b': AutocompleteSelect("b", attrs={
                'data-dropdownparent': '#exampleModal',
                'data-related': 'true',
                'data-pos': 1,
                'data-groupname': 'myabcde'
            }),
            'c': AutocompleteSelectMultiple("c", attrs={
                'data-dropdownparent': '#exampleModal',
                'data-related': 'true',
                'data-pos': 2,
                'data-groupname': 'myabcde'
            }),
            'd': AutocompleteSelect('d', attrs={
                'data-dropdownparent': '#exampleModal',
                'data-related': 'true',
                'data-pos': 3,
                'data-groupname': 'myabcde'
            }),
            'e': AutocompleteSelectMultiple('e', attrs={
                'data-dropdownparent': '#exampleModal',
                'data-related': 'true',
                'data-pos': 4,
                'data-groupname': 'myabcde',
            }),
        }
