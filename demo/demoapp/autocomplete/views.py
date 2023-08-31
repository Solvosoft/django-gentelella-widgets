from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView

from demoapp import models
from . import forms


class PeopleGroupAdd(CreateView):
    model = models.PeopleGroup
    success_url = reverse_lazy('pgroup-list')
    form_class = forms.PeopleGroupForm
    template_name = 'gentelella/index.html'


class PeopleGroupChange(UpdateView):
    model = models.PeopleGroup
    success_url = reverse_lazy('pgroup-list')
    form_class = forms.PeopleGroupForm
    template_name = 'gentelella/index.html'


class PeopleGroupList(ListView):
    model = models.PeopleGroup
    template_name = 'people_group_list.html'


class ABCDECreate(CreateView):
    model = models.ABCDE
    form_class = forms.ABCDEGroupForm
    success_url = reverse_lazy('abcde-list')
    template_name = 'gentelella/index.html'


class ABCDEChange(UpdateView):
    model = models.ABCDE
    success_url = reverse_lazy('abcde-list')
    form_class = forms.ABCDEGroupForm
    template_name = 'gentelella/index.html'


class ABCDEList(ListView):
    model = models.ABCDE
    template_name = 'ABCDE.html'
