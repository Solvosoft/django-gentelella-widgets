from django.forms import Textarea
from django.urls import reverse_lazy

from djgentelella.widgets.core import update_kwargs


class EditorTinymce(Textarea):
    template_name = 'gentelella/widgets/wysiwyg.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='wysiwyg form-control')
        attrs['data-option-image'] = reverse_lazy('tinymce_upload_image')
        attrs['data-option-video'] = reverse_lazy('tinymce_upload_video')
        super().__init__(attrs)


class VoiceEditorTinymce(EditorTinymce):
    """
    TinyMCE editor with a microphone button in its own toolbar for continuous
    voice dictation. Captures audio in the browser (Web Audio + VAD) and, as the
    user speaks, posts each speech segment to a transcription endpoint returning
    ``{"text": "..."}``; segments are inserted live via ``editor.insertContent``.
    ``data-mode`` selects the strategy: ``segments`` (default, live), ``single``
    (one request on stop) or ``hybrid`` (live segments then a whole-file rewrite
    on stop).

    ``url`` is the transcription endpoint (``voice_transcribe`` or a
    proxy). ``language`` sets ``data-language``. Optional biasing context can be
    provided with ``data-hotwords`` and ``data-initial-prompt`` attrs; the
    endpoint may forward or ignore them.
    """

    def __init__(self, attrs=None, extraskwargs=True, url=None, language=None):
        super().__init__(attrs, extraskwargs=extraskwargs)
        if url is not None:
            self.attrs['data-url'] = url
        if language is not None:
            self.attrs['data-language'] = language
