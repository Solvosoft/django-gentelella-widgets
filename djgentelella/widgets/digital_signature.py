import uuid
from django.forms import FileInput
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from djgentelella.widgets.core import update_kwargs


class DigitalSignatureInput(FileInput):
    template_name = 'gentelella/digital_signature/signature.html'
    input_type = 'file'


    def __init__(self, attrs=None,  extraskwargs=True, ws_url=None):
        attrs = attrs or {}

        attrs['data-ws-url'] = ws_url

        if extraskwargs:
            attrs = update_kwargs(
                attrs, self.__class__.__name__,)
        super().__init__(attrs)

