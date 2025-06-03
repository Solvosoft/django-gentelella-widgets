import base64
import logging
from io import BytesIO

from PIL import Image
from PIL.Image import Resampling
from channels.generic.websocket import JsonWebsocketConsumer
from django.contrib.staticfiles import finders
from django.utils.translation import gettext_lazy as _

from djgentelella.firmador_digital.utils import RemoteSignerClient
from djgentelella.serializers.firmador_digital import (
    WSRequest,
    InitialSignatureSerializer,
    CompleteSignatureSerializer, ValidateDocumentSerializer,
)

logger = logging.getLogger("djgentelella")


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
            if serializer.validated_data["action"] == "validate_document":
                return ValidateDocumentSerializer(data=content)

    def disconnect(self, close_code):
        super().disconnect(close_code)
        logger.info(f"Disconnect {close_code}")

    def receive_json(self, content, **kwargs):
        """
        Called with decoded JSON content.
        """
        socket_id = ""
        try:
            serializer = self.get_serializer(content)

            if serializer.is_valid():
                socket_id = serializer.validated_data['socket_id']
                match serializer.validated_data["action"]:
                    case "initial_signature":
                        self.do_initial_signature(serializer)
                    case "complete_signature":
                        self.do_complete_signature(serializer)
                    case "validate_document":
                        self.do_validate_document(serializer)
                    case _:
                        self.do_default(serializer)
            else:
                # errors when serializing data
                self.send_json({
                    "result": False,
                    "error": str(_("Invalid request.")),
                    "details": serializer.errors,
                    "status": 400,
                    "code": 11,
                    'socket_id': serializer.data.get('socket_id')
                })
                logger.error("Invalid request.")

        except Exception as e:
            # uncontrolled data serializing errors
            self.send_json({
                "result": False,
                "error": str(_("An unexpected error occurred.")),
                "details": str(e),
                "status": 500,
                "code": 999,
                "socket_id": socket_id
            })
            logger.error("An unexpected error occurred.", exc_info=e)

    def do_validate_document(self, serializer):
        signer = RemoteSignerClient(self.scope["user"])

        response = signer.validate_document(
            instance=serializer.validated_data["instance"],
        )

        response['socket_id'] = serializer.validated_data['socket_id']
        self.send_json(response)

    def do_initial_signature(self, serializer):
        signer = RemoteSignerClient(self.scope["user"])

        # data for the request to Firmador server
        response = signer.send_document_to_sign(
            instance=serializer.validated_data["instance"],
            usertoken=serializer.validated_data["card"],
            docsettings=serializer.validated_data["docsettings"],
        )

        response['socket_id'] = serializer.validated_data['socket_id']

        # remove signer image
        if "imageIcon" in response:
            del response["imageIcon"]

        # about writing the answer to add b64image
        logo_url = serializer.validated_data["logo_url"]
        if "b64image" in response and logo_url:
            response["b64image"] = self.get_logo_base64(logo_url)

        self.send_json(response)

    def do_complete_signature(self, serializer):
        try:
            signer = RemoteSignerClient(self.scope["user"])
            data = dict(serializer.validated_data)
            response = signer.complete_signature(data)
            self.send_json({"result": response,
                            'socket_id': serializer.validated_data['socket_id']})
        except Exception as e:
            logger.error("Complete the signature fail", exc_info=e)

    def do_default(self, serializer):
        pass

    def get_logo_base64(self, path_logo, target_width=128):
        if not path_logo:
            print("Do not have logo")
            return ""

        # Si la ruta contiene el prefijo /static/, lo removemos
        if path_logo.startswith('/static/'):
            path_logo = path_logo[len('/static/'):]

        # Buscar la ruta real del archivo en los directorios estáticos
        real_path = finders.find(path_logo)
        if not real_path:
            print("Logo file not found in static directories.")
            return ""

        try:
            with Image.open(real_path) as img:
                # Calcular la altura de forma proporcional
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
            logger.error("Reading logo fail", exc_info=e)
            return ""
