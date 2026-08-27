from django.conf import settings
from django.forms import Textarea
from django.urls import reverse_lazy
from django.utils.translation import get_language

from djgentelella.widgets.core import update_kwargs


class EditorTinymce(Textarea):
    template_name = 'gentelella/widgets/wysiwyg.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = attrs or {}
        attrs.setdefault('data-option-spellcheck', 'true')
        attrs.setdefault('data-option-lang', get_language() or settings.LANGUAGE_CODE)
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='wysiwyg form-control')
        # update_kwargs is what normally turns None into a dict, so without
        # this `EditorTinymce(extraskwargs=False)` died on the next line.
        attrs = attrs or {}
        attrs['data-option-image'] = reverse_lazy('tinymce_upload_image')
        attrs['data-option-video'] = reverse_lazy('tinymce_upload_video')
        super().__init__(attrs)


class VoiceEditorTinymce(EditorTinymce):
    """
    TinyMCE editor with a microphone button in its own toolbar for continuous
    voice dictation. Captures audio in the browser (Web Audio + VAD) and, as the
    user speaks, posts each speech segment to a transcription endpoint returning
    ``{"text": "..."}``; segments are inserted live via ``editor.insertContent``.

    Configured exactly like :class:`~djgentelella.widgets.core.VoiceDictation`
    -- same engine, same attributes. ``url`` and ``language`` are kwargs;
    ``data-mode`` (``segments`` | ``single`` | ``hybrid``), ``data-hotwords``,
    ``data-initial-prompt`` and the seven capture-tuning keys go through
    ``attrs``, so a project can add its own ``data-`` without the widget growing
    a kwarg per option::

        VoiceEditorTinymce(url=reverse_lazy('voice_transcribe'),
                           attrs={'data-mode': 'hybrid'})

    See ``VoiceDictation`` for what each attribute does.
    """

    def __init__(self, attrs=None, extraskwargs=True, url=None, language=None):
        # Written through self.attrs after super(), unlike core.VoiceDictation
        # which builds the dict first: the parent has its own attrs to add and
        # normalises None away, so there is nothing to write into before it.
        super().__init__(attrs, extraskwargs=extraskwargs)
        if url is not None:
            self.attrs['data-url'] = url
        if language is not None:
            self.attrs['data-language'] = language
