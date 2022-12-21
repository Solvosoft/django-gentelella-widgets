from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from demoapp.models import InputMask
from .forms import InputMaskForms


class InsertMask(CreateView):
    model = InputMask
    form_class = InputMaskForms
    template_name = 'gentelella/input_mask/inputs.html'
    success_url = reverse_lazy('input-mask-list')


class listMask(ListView):
    model = InputMask
    template_name = 'gentelella/input_mask/view_inputs.html'


class EditMask(UpdateView):
    model = InputMask
    form_class = InputMaskForms
    template_name = 'gentelella/input_mask/inputs.html'
    success_url = reverse_lazy('input-mask-list')
