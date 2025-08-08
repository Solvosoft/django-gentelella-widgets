import base64
import logging
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from djgentelella.firmador_digital.models import UserSignatureConfig, \
    get_signature_default, FORMATS_DATE, FONT_ALIGNMENT
from djgentelella.firmador_digital.signvalue_utils import ValueDSParser
from djgentelella.forms.forms import GTForm
from djgentelella.widgets import core as genwidgets
from djgentelella.widgets.core import FileInput

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
        initial="#FFFFFF",
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
    image = forms.ImageField(
        required=False,
        widget=FileInput,
        label=_("Signature image")
    )

    default_render_type = "as_grid"

    grid_representation = [
        [["contact"]],
        [["place"]],
        [["reason"]],
        [["image"], ["preview_image"]],
        [["dateFormat"], ["isVisibleSignature"]],
        [["fontSize"], ["fontColor"], ["fontAlignment"]],
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

    def preview_image(self):
        label = _("Image preview")
        src = static("gentelella/images/default.png")

        if self.instance and self.instance.config:
            image_b64 = self.instance.config.get("image")
            if image_b64 and image_b64.startswith("data:image"):
                src = image_b64

        return mark_safe(f"""
            <label for="image-preview"><strong>{label}:</strong></label><br>
            <div class="d-flex justify-content-center">
                <img id="image-preview" alt="{label}" src="{src}" style="max-height:100px; max-width:300px; display:block;">
            </div>
        """)

    def save(self, commit=True):
        data = get_signature_default()
        prev_image = self.instance.config.get("image")

        for key in data.keys():
            if key in self.cleaned_data:
                val = self.cleaned_data[key]
                if key == "image":
                    if isinstance(val, UploadedFile):
                        # el usuario subió un nuevo archivo
                        buffered = BytesIO()
                        for chunk in val.chunks():
                            buffered.write(chunk)
                        mime = val.content_type
                        b64 = base64.b64encode(buffered.getvalue()).decode()
                        val = f"data:{mime};base64,{b64}"
                    else:
                        # no se subió archivo nuevo → conservamos imagen anterior
                        val = prev_image

                if isinstance(data[key], str) and not isinstance(val, str):
                    val = str(val)
                data[key] = val

        self.instance.config = data
        return super().save(commit=commit)
