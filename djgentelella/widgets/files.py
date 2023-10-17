import json
from logging import getLogger
from pathlib import Path

from django.forms import FileInput
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe

from djgentelella.models import ChunkedUpload
from djgentelella.widgets.core import update_kwargs

logger = getLogger('djgentelella')


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
        if value:
            name = Path(value.name).name
            self.value = mark_safe(
                '{"name": "%(name)s", "display_name": "%(display_name)s", "url": "%(url)s" }' % {
                    'name': value.name,
                    'display_name': name,
                    'url': value.url})
            return self.value
        return ''

    def parse_value(self, value):
        dev = None
        try:
            dev = json.loads(value)
            if not ('url' in dev or 'token' in dev or 'actions' in dev):
                dev = None
        except json.JSONDecodeError as e:
            logger.warning("Json error parsing: " + repr(value))
        return dev

    def value_from_datadict(self, data, files, name):
        dev = None

        token = self.parse_value(data.get(name))
        if token:
            if 'actions' in token and token['actions'] == 'delete':
                return False
            if 'token' in token:
                tmpupload = ChunkedUpload.objects.filter(
                    upload_id=token['token']).first()
                if tmpupload:
                    dev = tmpupload.get_uploaded_file()
                    tmpupload.delete()
        return dev

    def value_omitted_from_data(self, data, files, name):
        return name not in data
