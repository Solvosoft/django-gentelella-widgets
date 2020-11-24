from django.forms import Textarea
from django.urls import reverse_lazy
import json
from djgentelella.widgets.core import update_kwargs
from django.conf import settings


class TextareaWysiwyg(Textarea):
    template_name = 'gentelella/widgets/wysiwyg.html'

    def __init__(self, attrs=None, extraskwargs=True):
        if extraskwargs:

            attrs = update_kwargs(attrs, self.__class__.__name__, base_class='form-control')
        attrs['data-option-image']=reverse_lazy('upload_image')
        super().__init__(attrs)
