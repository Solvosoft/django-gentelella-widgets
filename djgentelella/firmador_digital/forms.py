import base64
import json
import logging

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets

logger = logging.getLogger('djgentelella')


class CardForm(GTForm):
    card = forms.ChoiceField(choices=[], widget=genwidgets.Select, label=_("Card"))


class RenderValueForm(GTForm):
    value = forms.CharField(required=True)

    def get_json_file(self, value):
        jsondata = None
        try:
            instance = base64.b64decode(value.encode())
            jsondata = json.loads(instance.decode())
        except Exception as e:
            logger.error("Validation of value on digital signature fail", exc_info=e)
        return jsondata

    def clean_value(self):
        value = self.cleaned_data['value']
        jsondata = self.get_json_file(value)
        if not jsondata:
            raise ValidationError(
                _("Invalid value not encoded as b64 o json parser error"),
                code="invalid")
        return jsondata
