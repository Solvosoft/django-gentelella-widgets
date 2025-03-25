import logging

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from djgentelella.firmador_digital.signvalue_utils import ValueDSParser
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets

logger = logging.getLogger('djgentelella')


class CardForm(GTForm):
    card = forms.ChoiceField(choices=[], widget=genwidgets.Select, label=_("Card"))


class RenderValueForm(GTForm, ValueDSParser):
    value = forms.CharField(required=True)

    def clean_value(self):
        value = self.cleaned_data['value']
        jsondata = self.get_json_file(value)
        if not jsondata:
            raise ValidationError(
                _("Invalid value not encoded as b64 o json parser error"),
                code="invalid")
        return jsondata
