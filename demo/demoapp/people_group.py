from django.forms import ModelMultipleChoiceField, ModelChoiceField
from django.http import HttpResponse
from django.views.generic import CreateView, UpdateView, ListView
from django import forms
from demoapp.models import PeopleGroup
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets.selects import AutocompleteSelect, AutocompleteSelectMultiple

from django.db.models.fields.related import ManyToManyField

def formfield_callback_fnc(db_field, **kwargs):
    formfield = db_field.formfield(**kwargs)

    if 'widget' in kwargs:
        if kwargs['widget'].__name__ in ('AutocompleteSelect', 'AutocompleteSelectMultiple'):
            formfield._choices = []
    return formfield


class PeopleGroupForm(CustomForm, forms.ModelForm):
    formfield_callback = formfield_callback_fnc

    class Meta:
        model = PeopleGroup
        fields = '__all__'
        widgets = {
            'people': AutocompleteSelect("personbasename-list"),
            'comunities': AutocompleteSelectMultiple("comunitybasename-list")
        }




class PeopleGroupAdd(CreateView):
    model = PeopleGroup
    #fields = '__all__'
    success_url = '/pgroup/'
    form_class = PeopleGroupForm
    template_name = 'gentelella/index.html'

class PeopleGroupChange(UpdateView):
    model = PeopleGroup
    #fields = '__all__'
    success_url = '/pgroup/'
    form_class = PeopleGroupForm
    template_name = 'gentelella/index.html'

class PeopleGroupList(ListView):
    model = PeopleGroup
    template_name = 'people_group_list.html'


class PGorm(forms.ModelForm):
    formfield_callback = formfield_callback_fnc

    class Meta:
        model = PeopleGroup
        fields = ['people']
        widgets = {
            'people': AutocompleteSelectMultiple("personbasename-list"),
            'comunities': AutocompleteSelectMultiple("comunitybasename-list")
        }

def pgroup_test(request):
    pg = PGorm()
    print(str(pg))
    return HttpResponse("OK")