from django import forms

from djgentelella.models import ChunkedUpload
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as GTWidgets
from djgentelella.widgets.digital_signature import DigitalSignature
from django.utils.translation import gettext_lazy as _

class DigitalSignatureForm(GTForm, forms.ModelForm):

    class Meta:
        model = ChunkedUpload
        fields = ['file', 'filename']
        widgets = {
            'filename': forms.HiddenInput,
            'file': DigitalSignature
        }
