from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

FORMATS_DATE = [("dd/MM/yyyy hh:mm:ss a", "dd/MM/yyyy hh:mm:ss a"),
                ("yyyy/MM/dd HH:mm:ss", "yyyy/MM/dd HH:mm:ss"),
                ("MM/dd/yyyy hh:mm:ss a", "MM/dd/yyyy hh:mm:ss a"),
                ("dd-MM-yyyy", "dd-MM-yyyy"), ]

FONT_ALIGNMENT = (('NONE', _('None')), ('RIGHT', _('Right')), ('LEFT', _('Left')),
                  ('TOP', _('Top')), ('BOTTOM', _('Bottom')),)


def get_signature_default():
    return {"backgroundColor": "transparent", "cAdESLevel": "LTA", "contact": "",
            "country": "CR", "dateFormat": "dd/MM/yyyy hh:mm:ss a",
            "defaultSignMessage": "Esta es una representación gráfica únicamente,\nverifique la validez de la firma.",
            "font": "Nimbus Sans Regular", "fontAlignment": "None",
            "fontColor": "000000",
            "fontSize": "7", "image": "", "language": "es", "pAdESLevel": "LTA",
            "place": "", "portNumber": "3516", "reason": "", "signHeight": "33",
            "signWidth": "133", "signX": "40", "signY": "60", "xAdESLevel": "LTA",
            "isVisibleSignature": False, "hideSignatureAdvice": False, }


class UserSignatureConfig(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    config = models.JSONField(default=get_signature_default)
