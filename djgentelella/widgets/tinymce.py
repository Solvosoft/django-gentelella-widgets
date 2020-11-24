from django.forms import Textarea
from django.urls import reverse_lazy, NoReverseMatch
import json
from djgentelella.widgets.core import update_kwargs
from django.conf import settings


class EditorTinymce(Textarea):
    template_name = 'gentelella/widgets/wysiwyg.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:

            attrs = update_kwargs(attrs, self.__class__.__name__, base_class='wysiwyg form-control')
        attrs['data-option-image']=reverse_lazy('tinymce_upload_image')
        attrs['data-option-video']=reverse_lazy('tinymce_upload_video')
        super().__init__(attrs)
