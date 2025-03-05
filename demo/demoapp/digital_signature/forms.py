from django import forms
from django.conf import settings

from demoapp.models import DigitalSignature
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.digital_signature import DigitalSignatureInput

class DigitalSignatureForm(GTForm, forms.ModelForm):

    class Meta:
        model = DigitalSignature
        fields = ['file']
        widgets = {
            'file': DigitalSignatureInput(
                ws_url="%s%s" % (settings.FIRMADOR_WS, 'sign_document'),
                default_page = "last"
            )
        }
