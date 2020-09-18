from django.shortcuts import render
from django.urls import reverse_lazy
from .forms import ContactForm
from demoapp.models import Contact
from datetime import datetime

from django.views.generic import CreateView, ListView, UpdateView


class multi(CreateView):
    model = Contact
    form_class = ContactForm
    template_name = 'gentelella/multi/multi.html'
    success_url = reverse_lazy('input-mask-list')

class umulti(UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = 'gentelella/multi/multi.html'
    success_url = reverse_lazy('input-mask-list')
