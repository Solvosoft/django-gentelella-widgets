from django import forms
from django.urls import reverse_lazy
from demoapp.models import PeopleGroup, Person, PersonGroup
from djgentelella.forms.forms import GTForm
from djgentelella.models import MenuItem
from djgentelella.widgets.core import Select2Box, TextInput
from djgentelella.widgets.selects import AutocompleteSelect


"""class dataOptions(GTForm):
    mydata = forms.MultipleChoiceField(widget=Select2Box, choices=[[1, "primero"], [2, "segundo"], [3, "tercero"], [4, "cuarto, quinto, sexto, setimo y octavo"]])
    mymenu = forms.ModelMultipleChoiceField(widget=Select2Box(attrs={'data-url':reverse_lazy('personbasename-list'), 'data-addurl': reverse_lazy('select2box-personform')}), queryset=Person.objects.all()) """

class PersonSelect2BoxForm(GTForm, forms.ModelForm):
    class Meta:
        model = PersonGroup
        fields = '__all__'
        widgets = {
            'items': Select2Box(attrs={'data-url':reverse_lazy('choicebasename-list'), 'data-addurl': reverse_lazy('select2box-itemform')}),
            'persons': Select2Box(attrs={'data-url':reverse_lazy('personbasename-list'), 'data-addurl': reverse_lazy('select2box-personform')})
        }

class PeopleSelect2BoxForm(GTForm, forms.ModelForm):
    class Meta:
        model = PeopleGroup
        fields = '__all__'
        widgets = {
            'name': TextInput,
            'people': Select2Box(attrs={'data-url':reverse_lazy('personbasename-list'), 'data-addurl':reverse_lazy('select2box-group-personform')}),
            'comunities': Select2Box(attrs={'data-url':reverse_lazy('comunitybasename-list'), 'data-addurl':reverse_lazy('select2box-group-comunityform')}),
            'country': AutocompleteSelect('countrybasename')
        }
