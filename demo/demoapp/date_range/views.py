from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import DateRangeForms
from demoapp.models import DateRange
from datetime import datetime

from django.views.generic import CreateView


class CreateDate(CreateView):
    model = DateRange
    form_class = DateRangeForms
    template_name = 'gentelella/input_mask/inputs.html'
    success_url = reverse_lazy('input-mask-list')
