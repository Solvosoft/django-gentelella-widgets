from django.contrib import messages
from django.forms import formset_factory, modelformset_factory
from django.shortcuts import render

from demoapp.forms import PersonForm, CityForm
from demoapp.models import Person, Comunity
from djgentelella.forms.forms import GTFormSet, GTBaseModelFormSet


def add_formset(request):
    formset = formset_factory(PersonForm, formset=GTFormSet,
                              extra=4, max_num=5, validate_max=True, can_delete=True, can_order=True)
    fset = formset(prefix='pref')
    return render(request, 'formset.html', {'formset': fset})


def add_model_formset(request):
    formset = modelformset_factory(Comunity, form=CityForm, formset=GTBaseModelFormSet,
                                   can_delete=True)
    valid=True
    if request.method == 'POST':
        fset = formset(request.POST, queryset=Comunity.objects.all(), prefix='pff')
        valid=fset.is_valid()
        if valid:
            r = fset.save()
            messages.success(request, "Formset saved successfully")

    if valid:
        fset = formset(queryset=Comunity.objects.all(), prefix='pff')
   
    return render(request, 'modelformset.html', {'formset': fset})
