from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from .models_utils import upload_files


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
    }


class UserSignatureConfig(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    config = models.JSONField(default=get_signature_default)


class DocumentSignature(models.Model):
    code = models.CharField(max_length=100, unique=True, verbose_name=_("Code"))
    name = models.CharField(max_length=100, unique=True, verbose_name=_("Name"))
    document = models.FileField(
        blank=True,
        null=True,
        upload_to=upload_files,
        verbose_name=_("Document"),
    )
    created_on = models.DateTimeField(auto_now_add=True, verbose_name=_("Created on"))
    modified_on = models.DateTimeField(auto_now=True, verbose_name=_("Modified on"))

    def __str__(self):
        return "File( code: %s, name: %s)" % (self.code, self.name)
