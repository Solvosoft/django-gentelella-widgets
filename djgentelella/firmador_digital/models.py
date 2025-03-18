from django.contrib.auth import get_user_model
from django.db import models

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
