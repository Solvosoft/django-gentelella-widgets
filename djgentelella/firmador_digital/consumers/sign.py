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
from ..utils import RemoteSignerClient


class SignConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = None

    def connect(self):
        self.accept()
        self.signclient = RemoteSignerClient(None)

    def get_serializer(self, content):
        serializer = WSRequest(data=content)

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
            if serializer.is_valid():
                match serializer.validated_data["action"]:
                    case "initial_signature":
                        self.do_initial_signature(serializer)
                    case "complete_signature":
                        self.do_complete_signature(serializer)
                    case _:
                        self.do_default(serializer)
            else:
                print(serializer.errors)
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
        signer = RemoteSignerClient(self.scope["user"])
        # peticion a firmador
        response = signer.send_document_to_sign(
            serializer.validated_data["instance"],
            serializer.validated_data["card"],
            serializer.validated_data["docsettings"],
        )
        # elimina imagen de firmador
        if "imageIcon" in response:
            del response["imageIcon"]

        # sobre escribir la respuesta para agregar b64image
        if "b64image" in response:
            org = serializer.validated_data["organization"]
            response["b64image"] = self.get_logo_base64(org)

        self.send_json(response)

    def do_complete_signature(self, serializer):
        signer = RemoteSignerClient(self.scope["user"])
        data = dict(serializer.validated_data)
        instance = data.pop("instance")
        response = signer.complete_signature(instance, data)
        self.send_json({"result": response})

    def do_default(self, serializer):
        pass

    def get_logo_base64(self, org, target_width=128) :

        if not org.logo:
            return ""

        path = org.logo.path

        try:
            with Image.open(path) as img:
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



