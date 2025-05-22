from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView

from demoapp import models
from . import forms


class ImageAdd(CreateView):
    model = models.Img
    success_url = reverse_lazy('imgselect-list')
    form_class = forms.ImageForm
    template_name = 'gentelella/index.html'


class ImageChange(UpdateView):
    model = models.Img
    success_url = reverse_lazy('imgselect-list')
    form_class = forms.ImageForm
    template_name = 'gentelella/index.html'


class ImageList(ListView):
    model = models.Img
    template_name = 'gentelella/select_images/list.html'
