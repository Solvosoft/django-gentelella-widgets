from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import MultiwidgetForm
from demoapp.models import Multiwidget
from datetime import datetime

from django.views.generic import CreateView, ListView, UpdateView


class InsertMultiwidget(CreateView):
    model = Multiwidget
    form_class = MultiwidgetForm
    template_name = 'gentelella/multiwidget/inputs.html'
    success_url = reverse_lazy('multiwidget-list')

class UpdateMultiwidget(UpdateView):
    model = Multiwidget
    form_class = MultiwidgetForm
    template_name = 'gentelella/multiwidget/inputs.html'
    success_url = reverse_lazy('multiwidget-list')

class listMultiwidget(ListView):
    model = Multiwidget
    template_name = 'gentelella/multiwidget/view_inputs.html'
