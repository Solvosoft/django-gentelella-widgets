from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.db import models

FORMATS_DATE = [
    ("dd/MM/yyyy hh:mm:ss a", "dd/MM/yyyy hh:mm:ss a"),
    ("yyyy/MM/dd HH:mm:ss",   "yyyy/MM/dd HH:mm:ss"),
    ("MM/dd/yyyy hh:mm:ss a", "MM/dd/yyyy hh:mm:ss a"),
    ("dd-MM-yyyy",            "dd-MM-yyyy"),
]

FONT_ALIGNMENT = [
    ("LEFT", _("LEFT")),
    ("CENTER", _("CENTER")),
    ("RIGHT", _("RIGHT")),
]

FONT_CHOICES = [
    ("Nimbus Sans Regular", "Nimbus Sans Regular"),
    ("Nimbus Sans Bold", "Nimbus Sans Bold"),
    ("Nimbus Sans Italic", "Nimbus Sans Italic"),
    ("Nimbus Sans Bold Italic", "Nimbus Sans Bold Italic"),
]

def get_signature_default():
    return {
        "backgroundColor": "transparente",
        "cAdESLevel": "LTA",
        "contact": "",
        "country": "CR",
        "dateFormat": "dd/MM/yyyy hh\:mm\:ss a",
        "defaultSignMessage": "Esta es una representación gráfica únicamente,\nverifique la validez de la firma.",
        "font": "Nimbus Sans Regular",
        "fontAlignment": "RIGHT",
        "fontColor": "000000",
        "fontSize": "7",
        "image": "",
        "language": "es",
        "pAdESLevel": "LTA",
        "place": "",
        "portNumber": "3516",
        "reason": "",
        "signHeight": "33",
        "signWidth": "133",
        "signX": "40",
        "signY": "60",
        "xAdESLevel": "LTA",
        "isVisibleSignature": False,
    }


class UserSignatureConfig(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    config = models.JSONField(default=get_signature_default)
