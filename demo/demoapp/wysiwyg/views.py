from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DetailView

from demoapp.models import WysiwygModel
from .forms import EditorTinymce


class InsertTinymce(CreateView):
    model = WysiwygModel
    form_class = EditorTinymce
    template_name = 'gentelella/editorTinymce/inputs.html'
    success_url = reverse_lazy('tinymce-list')


class ListTinymce(ListView):
    model = WysiwygModel
    template_name = 'gentelella/editorTinymce/list_info.html'


class EditTinymce(UpdateView):
    model = WysiwygModel
    form_class = EditorTinymce
    template_name = 'gentelella/editorTinymce/inputs.html'
    success_url = reverse_lazy('tinymce-list')


class DetailTinymce(DetailView):
    model = WysiwygModel
    template_name = 'gentelella/editorTinymce/show.html'
    success_url = reverse_lazy('tinymce-list')
