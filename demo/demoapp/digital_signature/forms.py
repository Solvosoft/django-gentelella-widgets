from django import forms
from django.conf import settings

from demoapp.models import DigitalSignature
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.digital_signature import DigitalSignatureInput
from django.utils.translation import gettext_lazy as _

class DigitalSignatureForm(GTForm, forms.ModelForm):

    class Meta:
        model = DigitalSignature
        fields = ['file']
        widgets = {
            'file': DigitalSignatureInput(
                ws_url="%s" % settings.FIRMADOR_WS_URL,
                cors="%s" % settings.FIRMADOR_CORS,
                title=_("Widget Digital Signature"),
                default_page = "last"
            )
        }
