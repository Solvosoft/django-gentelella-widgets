from django import forms
from django.conf import settings

from djgentelella.models import ChunkedUpload
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.digital_signature import DigitalSignatureInput

class DigitalSignatureForm(GTForm, forms.ModelForm):

    class Meta:
        model = ChunkedUpload
        fields = ['file', 'filename']
        widgets = {
            'filename': forms.HiddenInput,
            'file': DigitalSignatureInput(
                ws_url=settings.FIRMADOR_WS
            )
        }
