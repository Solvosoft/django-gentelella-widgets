from django.urls import reverse_lazy

from .forms import dataOptions, PeopleSelect2BoxForm
from django.views.generic import FormView, CreateView, UpdateView, ListView
from ..models import PeopleGroup


class formSelect2BoxView(FormView):
    form_class = dataOptions
    template_name = 'gentelella/index.html'

class Select2BoxGroupAdd(CreateView):
    model = PeopleGroup
    success_url = reverse_lazy('select2box-group-list')
    form_class = PeopleSelect2BoxForm
    template_name = 'gentelella/index.html'


class Select2BoxGroupChange(UpdateView):
    model = PeopleGroup
    success_url = reverse_lazy('select2box-group-list')
    form_class = PeopleSelect2BoxForm
    template_name = 'gentelella/index.html'


class Select2BoxGroupList(ListView):
    model = PeopleGroup
    template_name = 'people_group_select2box.html'
