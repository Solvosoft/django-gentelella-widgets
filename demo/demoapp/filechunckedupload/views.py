from django.urls import reverse_lazy
from .forms import ChunkedUploadItemForm
from demoapp.models import ChunkedUploadItem
from django.views.generic import CreateView, ListView, UpdateView


class Addchunkedupload(CreateView):
    model = ChunkedUploadItem
    form_class = ChunkedUploadItemForm
    template_name = 'gentelella/chunkedupload/form-chunkedupload.html'
    success_url = reverse_lazy('chunkeduploaditem-list')


class Listchunkedupload(ListView):
    model = ChunkedUploadItem
    template_name = 'gentelella/chunkedupload/list-chunkedupload.html'

    def get_queryset(self):
        return self.model.objects.all()


class Updatechunkedupload(UpdateView):
    model = ChunkedUploadItem
    form_class = ChunkedUploadItemForm
    template_name = 'gentelella/chunkedupload/form-chunkedupload.html'
    success_url = reverse_lazy('chunkeduploaditem-list')
