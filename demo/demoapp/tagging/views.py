from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import TaggingForm
from demoapp.models import TaggingModel
from datetime import datetime

from django.views.generic import CreateView, ListView, UpdateView


class InsertTagging(CreateView):
    model = TaggingModel
    form_class = TaggingForm
    template_name = 'gentelella/input_tagging/inputs.html'
    success_url = reverse_lazy('input_tagging-list')

class ListTagging(ListView):
    model = TaggingModel
    template_name = 'gentelella/input_tagging/view_inputs.html'


class EditTagging(UpdateView):
    model = TaggingModel
    form_class = TaggingForm
    template_name = 'gentelella/input_tagging/inputs.html'
    success_url = reverse_lazy('input_tagging-list')
