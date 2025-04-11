import logging

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from djgentelella.firmador_digital.models import UserSignatureConfig, \
    get_signature_default, FORMATS_DATE, FONT_ALIGNMENT, FONT_CHOICES
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


class SignatureConfigForm(GTForm, forms.ModelForm):
    backgroundColor = forms.CharField(
        max_length=50,
        widget=genwidgets.ColorInput,
        required=True,
        label=_("Background color")
    )
    contact = forms.CharField(
        required=False,
        max_length=100,
        widget=genwidgets.TextInput,
        label=_("Contact")
    )
    dateFormat = forms.ChoiceField(
        widget=genwidgets.Select,
        required=True,
        choices=FORMATS_DATE,
        label=_("Date format")
    )

    defaultSignMessage = forms.CharField(
        widget=genwidgets.Textarea,
        required=False,
        max_length=100,
        label=_("Signature message")
    )
    # font = forms.ChoiceField(
    #     required=True,
    #     widget=genwidgets.Select,
    #     label=_("Font"),
    #     choices=FONT_CHOICES
    # )
    fontAlignment = forms.ChoiceField(
        choices=FONT_ALIGNMENT,
        widget=genwidgets.Select,
        required=True,
        label=_("Font alignment")
    )
    fontColor = forms.CharField(
        max_length=50,
        widget=genwidgets.ColorInput,
        required=True,
        label=_("Font color"),
    )
    fontSize = forms.IntegerField(
        min_value=5,
        max_value=28,
        initial=7,
        widget=genwidgets.NumberInput,
        label=_("Font size")
    )
    place = forms.CharField(
        required=False,
        max_length=100,
        widget=genwidgets.TextInput,
        label=_("Place")
    )
    reason = forms.CharField(
        required=False,
        max_length=100,
        widget=genwidgets.TextInput,
        label=_("Reason")
    )
    isVisibleSignature = forms.BooleanField(
        required=False,
        widget=genwidgets.YesNoInput,
        label=_("Visible signature")
    )

    default_render_type = "as_grid"

    grid_representation = [
        [["contact"]],
        [["place"]],
        [["reason"]],
        # [["dateFormat"], ["font"]],
        [["dateFormat"], ["isVisibleSignature"]],
        [["fontSize"], ["fontColor"], ["backgroundColor"], ["fontAlignment"]],
        # [["isVisibleSignature"]],
        [["defaultSignMessage"]],
    ]

    class Meta:
        model = UserSignatureConfig
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        cfg = self.instance.config if getattr(self.instance, "config",
                                              None) else get_signature_default()
        for key, value in cfg.items():
            if key in self.fields:
                self.fields[key].initial = value

    def save(self, commit=True):
        data = get_signature_default()
        for key in data.keys():
            if key in self.cleaned_data:
                val = self.cleaned_data[key]

                if isinstance(data[key], str) and not isinstance(val, str):
                    val = str(val)
                data[key] = val
        self.instance.config = data
        return super().save(commit=commit)
