from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import ExampleForm
from demoapp.models import Multiwidget
from datetime import datetime

from django.views.generic import CreateView, ListView, UpdateView


class InsertMultiwidget(CreateView):
    model = Multiwidget
    form_class = ExampleForm
    template_name = 'gentelella/multi/multi.html'
    success_url = reverse_lazy('multiwidget-list')

class UpdateMultiwidget(UpdateView):
    model = Multiwidget
    form_class = ExampleForm
    template_name = 'gentelella/multi/multi.html'
    success_url = reverse_lazy('multiwidget-list')

class listMultiwidget(ListView):
    model = Multiwidget
    template_name = 'gentelella/multi/view-multi.html'
