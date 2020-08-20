from django.forms import formset_factory
from django.shortcuts import render

from demoapp.forms import PersonForm
from djgentelella.forms.forms import GTFormSet


def add_formset(request):
    formset = formset_factory(PersonForm, formset=GTFormSet,
                              extra=4, max_num=5, validate_max=True, can_delete=True, can_order=True)
    fset = formset(prefix='pref')
    return render(request, 'formset.html', {'formset': fset})