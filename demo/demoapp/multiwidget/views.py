from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView

from demoapp import models
from demoapp.multiwidget import forms


class MultiWidgetAddView(CreateView):
    model = models.MultiWidgetModel
    success_url = reverse_lazy('multiwidget-list')
    form_class = forms.MultiWidgetForm
    template_name = 'gentelella/index.html'


class MultiWidgetChangeView(UpdateView):
    model = models.MultiWidgetModel
    success_url = reverse_lazy('multiwidget-list')
    form_class = forms.MultiWidgetForm
    template_name = 'gentelella/index.html'


class MultiWidgetListView(ListView):
    model = models.MultiWidgetModel
    template_name = 'multiwidget.html'
