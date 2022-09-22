from djgentelella.models import ChunkedUpload
from django.forms import FileInput
from django.urls import reverse_lazy

from djgentelella.widgets.core import update_kwargs


class FileChunkedUpload(FileInput):
    input_type = 'file'
    needs_multipart_form = True
    template_name = 'gentelella/widgets/chunkedupload.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='djgentelella-file-input form-control')
        if 'data-href' not in attrs:
            attrs.update({'data-href': reverse_lazy('upload_file_view')})
        if 'data-done' not in attrs:
            attrs['data-done'] = reverse_lazy('upload_file_done')
        super().__init__(attrs)

    def format_value(self, value):
        """File input never renders a value."""
        return value

    def value_from_datadict(self, data, files, name):
        dev = None
        token = data.get(name)
        if token == '0':
            return False
        tmpupload = ChunkedUpload.objects.filter(upload_id=token).first()
        if tmpupload:
            dev = tmpupload.get_uploaded_file()
            tmpupload.delete()
        return dev

    def value_omitted_from_data(self, data, files, name):
        return name not in data
