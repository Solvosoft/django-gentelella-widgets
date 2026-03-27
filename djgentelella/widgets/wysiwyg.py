from django.conf import settings
from django.forms import Textarea
from django.urls import reverse_lazy
from django.utils.translation import get_language

from djgentelella.widgets.core import update_kwargs


class TextareaWysiwyg(Textarea):
    template_name = 'gentelella/widgets/wysiwyg.html'

    def __init__(self, attrs=None, extraskwargs=True):
        attrs = attrs or {}
        attrs.setdefault("data-option-spellcheck", "true")
        attrs.setdefault("data-option-lang", get_language() or settings.LANGUAGE_CODE)
        if extraskwargs:
            attrs = update_kwargs(attrs, self.__class__.__name__,
                                  base_class='wysiwyg form-control')
        attrs['data-option-image'] = reverse_lazy('tinymce_upload_image')
        attrs['data-option-video'] = reverse_lazy('tinymce_upload_video')
        super().__init__(attrs)