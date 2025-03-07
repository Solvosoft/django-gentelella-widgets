import base64
import json
import os
from io import BytesIO
from PIL import Image, ImageOps
from PIL.Image import Resampling

from channels.generic.websocket import WebsocketConsumer, JsonWebsocketConsumer
from django.utils.translation import gettext_lazy as _
from djgentelella.serializers.firmador_digital import (
    WSRequest,
    InitialSignatureSerializer,
    CompleteSignatureSerializer,
)
# from ..utils import RemoteSignerClient
from djgentelella.firmador_digital.utils import RemoteSignerClient


class SignConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = None

    def connect(self):
        self.accept()
        self.signclient = RemoteSignerClient(None)

    def get_serializer(self, content):
        serializer = WSRequest(data=content)
        print("SignConsumer - get_serializer", content)

        if serializer.is_valid():
            if serializer.validated_data["action"] == "initial_signature":
                return InitialSignatureSerializer(data=content)
            if serializer.validated_data["action"] == "complete_signature":
                return CompleteSignatureSerializer(data=content)

    def disconnect(self, close_code):
        super().disconnect(close_code)

    def receive_json(self, content, **kwargs):
        """
        Called with decoded JSON content.
        """
        try:
            serializer = self.get_serializer(content)
            print("SignConsumer - receive_json", serializer)
            if serializer.is_valid():
                print(serializer.validated_data["action"])
                match serializer.validated_data["action"]:
                    case "initial_signature":
                        self.do_initial_signature(serializer)
                    case "complete_signature":
                        print("Entro aca - complete_signature")
                        self.do_complete_signature(serializer)
                    case _:
                        self.do_default(serializer)
            else:
                print("SignConsumer - receive_json - errors", serializer.errors)
                # errores al serializar datos
                self.send_json({
                    "result": False,
                    "error": str(_("Invalid request.")),
                    "details": serializer.errors,
                    "status": 400,
                    "code": 11,
                })

        except Exception as e:
            # errores no controlados del serializar de datos
            self.send_json({
                "result": False,
                "error": str(_("An unexpected error occurred.")),
                "details": str(e),
                "status": 500,
                "code": 999,
            })

    def do_initial_signature(self, serializer):
        print(self.scope)
        print("do_initial_signature - user", self.scope["user"])
        signer = RemoteSignerClient(self.scope["user"])
        # peticion a firmador
        response = signer.send_document_to_sign(
            serializer.validated_data["instance"],
            serializer.validated_data["card"],
            serializer.validated_data["docsettings"],
        )

        print("do_initial_signature", response)

        print(serializer.validated_data["instance"].pk)

        # elimina imagen de firmador
        if "imageIcon" in response:
            del response["imageIcon"]

        # sobre escribir la respuesta para agregar b64image
        logo_url = serializer.validated_data["logo_url"]
        if "b64image" in response and logo_url:
            response["b64image"] = self.get_logo_base64(logo_url)

        print("SignConsumer - do_initial_signature", response)

        self.send_json(response)

    def do_complete_signature(self, serializer):
        print("do_complete_signature - user", self.scope["user"])
        signer = RemoteSignerClient(self.scope["user"])
        data = dict(serializer.validated_data)
        # instance = data.pop("instance")
        # response = signer.complete_signature(instance, data)
        response = signer.complete_signature(data)
        self.send_json({"result": response})

    def do_default(self, serializer):
        pass

    def get_logo_base64(self, path_logo, target_width=128):

        if not path_logo:
            print("Do not have logo")
            return ""

        try:
            with Image.open(path_logo) as img:
                # calcular la altura de forma proporcional
                ratio = target_width / float(img.width)
                target_height = int(img.height * ratio)

                # Redimensionar
                img = img.resize((target_width, target_height), Resampling.LANCZOS)

                # Guardar en memoria
                buffer = BytesIO()
                img.save(buffer, format='PNG')

                # Convertir a base64
                b64_logo = base64.b64encode(buffer.getvalue()).decode()
                return b64_logo

        except Exception as e:
            print("Error leyendo logo:", e)
            return ""
