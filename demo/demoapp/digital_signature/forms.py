from django import forms

from djgentelella.models import ChunkedUpload
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as GTWidgets
from django.utils.translation import gettext_lazy as _

class DigitalSignatureForm(GTForm, forms.ModelForm):

    class Meta:
        model = ChunkedUpload
        fields = ['file', 'filename']
        widgets = {
            'filename': GTWidgets.TextInput,
            'file': GTWidgets.FileInput
        }
