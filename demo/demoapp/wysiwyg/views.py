from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import WysiwygForm
from demoapp.models import WysiwygModel
from datetime import datetime
from django.views.generic import CreateView, ListView, UpdateView


class InsertWysiwyg(CreateView):
    model = WysiwygModel
    form_class = WysiwygForm
    template_name = 'gentelella/wysiwyg/inputs.html'
    success_url = reverse_lazy('wysiwyg-list')

class ListWysiwyg(ListView):
    model = WysiwygModel
    template_name = 'gentelella/wysiwyg/list_info.html'


class EditWysiwyg(UpdateView):
    model = WysiwygModel
    form_class = WysiwygForm
    template_name = 'gentelella/wysiwyg/inputs.html'
    success_url = reverse_lazy('wysiwyg-list')
