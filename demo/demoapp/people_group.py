from django.views.generic import CreateView, UpdateView, ListView
from django import forms
from demoapp.models import PeopleGroup
from djgentelella.forms.forms import CustomForm
from djgentelella.widgets.selects import AutocompleteSelect


class PeopleGroupForm(CustomForm, forms.ModelForm):
    class Meta:
        model = PeopleGroup
        fields = '__all__'
        widgets = {
            'people': AutocompleteSelect(baseurl="personbasename-list")
        }

class PeopleGroupAdd(CreateView):
    model = PeopleGroup
    #fields = '__all__'
    success_url = '/'
    form_class = PeopleGroupForm
    template_name = 'gentelella/index.html'

class PeopleGroupChange(UpdateView):
    model = PeopleGroup
    #fields = '__all__'
    success_url = '/'
    form_class = PeopleGroupForm
    template_name = 'gentelella/index.html'

class PeopleGroupList(ListView):
    model = PeopleGroup
    template_name = 'people_group_list.html'