import json
from logging import getLogger
from pathlib import Path

from django.forms import FileInput
from django.urls import reverse_lazy

from djgentelella.models import ChunkedUpload
from djgentelella.widgets.core import (
    UserUploadMixin,
    js_widget_name,
    update_kwargs,
    upload_token,
)

logger = getLogger('djgentelella')

# Escapes that keep a JSON text inert wherever it ends up in HTML: inside an
# attribute it is escaped once more by the template, inside a <script> nothing
# in it can close the tag.
JSON_HTML_ESCAPES = {ord('<'): '\\u003c', ord('>'): '\\u003e', ord('&'): '\\u0026'}


class FileChunkedUpload(FileInput):
    """Upload a file in chunks; the form gets the file of the posted token.

    The token is resolved **whoever uploaded the file** (see
    :meth:`get_upload`): who attaches or deletes a document does not have to
    be who uploaded it. :class:`UserFileChunkedUpload` takes only the user's
    own, finished uploads.
    """

    input_type = 'file'
    needs_multipart_form = True
    template_name = 'gentelella/widgets/chunkedupload.html'
    #: The name the javascript initializes it by, kept by the subclasses.
    js_widget = 'FileChunkedUpload'
    #: Delete the upload once the form takes its file. A wizard
    #: (:mod:`djgentelella.wizard`) turns it off on its forms: it validates a
    #: step more than once and deletes the uploads when it finishes.
    consume_upload = True

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(
                attrs,
                js_widget_name(self),
                base_class='djgentelella-file-input form-control',
            )
        if attrs is None:
            attrs = {}
        if 'data-href' not in attrs:
            attrs.update({'data-href': reverse_lazy('upload_file_view')})
        if 'data-done' not in attrs:
            attrs['data-done'] = reverse_lazy('upload_file_done')
        super().__init__(attrs)

    def format_value(self, value):
        """The stored file as ``{"name", "display_name", "url"}`` JSON.

        Not marked safe: the template escapes it into the ``value`` attribute
        and the browser gives the javascript the exact JSON back.
        """
        if value and not hasattr(value, 'url'):
            # A file just taken from an upload (a bound form shown again):
            # it has no URL yet.
            return ''
        if value:
            self.value = json.dumps({
                'name': str(value.name),
                'display_name': Path(value.name).name,
                'url': str(value.url),
            }).translate(JSON_HTML_ESCAPES)
            return self.value
        return ''

    def parse_value(self, value):
        dev = upload_token(value)
        if dev is None:
            if value:
                logger.warning('Json error parsing: %r', value)
            return None
        if not ('url' in dev or 'token' in dev or 'actions' in dev):
            dev = None
        return dev

    def get_upload(self, token):
        """The ``ChunkedUpload`` of ``token``, **whoever uploaded it**, in
        whatever state.

        On purpose: who attaches the file does not have to be who uploaded
        it. :class:`UserFileChunkedUpload` overrides this to take only the
        finished uploads of its user.
        """
        return ChunkedUpload.objects.filter(upload_id=token).first()

    def upload_value(self, upload):
        """The value of the field for ``upload``: its file. The upload is
        deleted (unless :attr:`consume_upload` is off), so a token is used
        once."""
        dev = upload.get_uploaded_file()
        if self.consume_upload:
            upload.delete()
        return dev

    def value_from_datadict(self, data, files, name):
        token = self.parse_value(data.get(name))
        if token:
            if token.get('actions') == 'delete':
                return False
            if isinstance(token.get('token'), str):
                upload = self.get_upload(token['token'])
                if upload is not None:
                    return self.upload_value(upload)
        return None

    def value_omitted_from_data(self, data, files, name):
        return name not in data


class UserFileChunkedUpload(UserUploadMixin, FileChunkedUpload):
    """:class:`FileChunkedUpload` that takes only the uploads of its
    ``user``, and only once they finished.

    The token of another user, or of an unfinished upload, gives ``None``
    and deletes nothing. The user comes from the form
    (:class:`~djgentelella.forms.forms.UserScopedUploadsMixin`) or from the
    widget itself (``UserFileChunkedUpload(user=request.user)``). The
    javascript and the template are those of :class:`FileChunkedUpload`.
    """

    js_widget = 'FileChunkedUpload'
