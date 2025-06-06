"""
DigitalSignatureForm is a simple example form demonstrating the use of the
DigitalSignatureInput widget for handling digital signatures.

This form is intended to be used with a DigitalSignature model that contains
a 'file' field to store the signed document or signature data.

The DigitalSignatureInput widget accepts several key parameters:

    - title (str):
        A short, human-readable title for the signature widget. In this example,
        it is set to "Widget Digital Signature". This title is used to label or
        describe the widget in the UI. This parameter is optional.

    - default_page (str or int):
        Indicates which page of the PDF should be displayed by default in the widget.
        Acceptable values are:
            • "first" – to show the first page,
            • "last" – to show the last page,
            • A positive integer (e.g., 1, 2, 3, etc.) – to show a specific page.
        In this example, it is set to "last". This parameter is optional.

    - ws_url (str, optional):
        The WebSocket URL for the digital signature service. If not provided, the widget
        will attempt to retrieve the value from the Django settings (FIRMADOR_WS_URL). This
        parameter is critical for establishing the connection with the signing service.


"""

from django import forms
from django.utils.translation import gettext_lazy as _

from demoapp.models import DigitalSignature
from djgentelella.forms.forms import GTForm
from djgentelella.widgets.core import FileInput, TextInput
from djgentelella.widgets.digital_signature import DigitalSignatureInput


class DigitalSignatureAddForm(GTForm, forms.ModelForm):
    class Meta:
        model = DigitalSignature
        fields = ['filename', 'file']
        widgets = {
            'filename': TextInput,
            'file': FileInput
        }


class DigitalSignatureForm(GTForm, forms.ModelForm):
    class Meta:
        model = DigitalSignature
        fields = ['file']
        widgets = {
            'file': DigitalSignatureInput(
                title=_("Widget Digital Signature"),
                default_page="last",
                render_basename="digital_signature_file_api"
            )
        }
