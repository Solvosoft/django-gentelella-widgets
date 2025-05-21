from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from demoapp.models import  Img
from .forms import ImageForm


class InsertImg(CreateView):
    model = Img
    form_class = ImageForm
    template_name = 'gentelella/select_images/input.html'
    success_url = reverse_lazy('select-images-list')


class EditImg(UpdateView):
    model = Img
    form_class = ImageForm
    template_name = 'gentelella/select_images/input.html'
    success_url = reverse_lazy('select-images-list')
