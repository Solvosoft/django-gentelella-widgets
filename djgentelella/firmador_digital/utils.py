import requests
import base64

from django.utils.translation import gettext_lazy as _
from django.conf import settings
import logging

from django.core.files.base import ContentFile
from django.utils.timezone import now
from requests import HTTPError, Timeout, RequestException

logger = logging.getLogger(__name__)

class RemoteSignerClient:
    def __init__(self, user):
        self.user = user

    def load_settings(self, docsettings):
        from djgentelella.firmador_digital.models import UserSignatureConfig
        sc = UserSignatureConfig.objects.filter(user=self.user).first()

        #! Agergar validacion para indicar que el usuario no tiene configuracion

        settings = {}
        settings.update(sc.config)
        settings.update(docsettings)
        return settings

    def load_certificate(self, certtoken):
        return certtoken["certificate"]

    def get_b64document(self, document):
        return base64.b64encode(document.file.read()).decode()

    def send_document_to_sign(self, instance, usertoken, docsettings):
        # print("send_document_to_sign 1", instance) # instancia str
        # print("send_document_to_sign 2", usertoken) #info de certificado
        print("send_document_to_sign 3", docsettings) # document settings

        b64doc = self.get_b64document(instance)
        # print(b64doc)
        files = {
            "b64Document": b64doc,
            "DocumentExtension": ".pdf",
            "settings": self.load_settings(docsettings),
            "certToken": self.load_certificate(usertoken),
        }
        headers = {"firmador-api": str(instance.pk)}
        response = requests.post(
            settings.FIRMADOR_SIGN_URL, json=files, headers=headers
        )
        return response.json()

    def _finalize_signature(self, data_to_sign, task):
        result = None
        error_msg = _("An unexpected error occurred during the signing process.")

        try:
            logger.info("Sending request to signing service")
            response = requests.post(settings.FIRMADOR_SIGN_COMPLETE, json=data_to_sign)
            response.raise_for_status()
            logger.info("Successfully finalized signature for the task.")
            result = response.json()
        except HTTPError as errh:
            logger.error(
                "HTTPError during signature finalization for task %s: %s",
                task,
                str(errh),
            )
            error_msg = _(
                "An error occurred while communicating with the signing service."
            )
            result = self.get_error_response(error_msg, str(errh), 502, 2)

        except ConnectionError as errc:
            logger.error(
                "ConnectionError during signature finalization for task %s: %s",
                task,
                str(errc),
            )
            error_msg = _("Unable to connect to the signing service.")
            result = self.get_error_response(error_msg, str(errc), 503, 2)
        except Timeout as errt:
            logger.error(
                "Timeout during signature finalization for task %s: %s", task, str(errt)
            )
            error_msg = _("The request to the signing service timed out.")
            result = self.get_error_response(error_msg, str(errt), 408, 12)
        except RequestException as err:
            logger.error(
                "RequestException during signature finalization for task %s: %s",
                task,
                str(err),
            )
            error_msg = _("An exception ocurred el request to the signing service.")
            result = self.get_error_response(error_msg, str(err), 500, 999)
        except Exception as err:
            logger.error(
                "Exception during signature finalization for task %s: %s",
                task,
                str(err),
            )
            error_msg = _("An unexpected error occurred during the signing process.")
            result = self.get_error_response(error_msg, str(err), 500, 999)

        return result

    def get_error_response(self, error_msg, details, status, code):
        return {
            "result": False,
            "error": error_msg,
            "details": details,
            "status": status,
            "code": code,
        }

    # def complete_signature(self, instance, data_to_sign):
    def complete_signature(self, data_to_sign):
        print("complete_signature 1", data_to_sign)

        datatosign = {
            "signature": data_to_sign["signature"],
            "documentid": data_to_sign["documentid"],
            "certificate": data_to_sign["certificate"],
        }
        instance = data_to_sign["instance"]
        doc_info = self._finalize_signature(datatosign, instance)
        if doc_info:
            instance.file = self.convert_to_django_file(
                doc_info["bytes"],
                "%s_%s_%s.pdf"
                % (
                    instance.pk,
                    self.user.pk,
                    now().strftime("%m%d%Y"),
                ),
            )
            instance.save()
            return True
        return False

    def convert_to_django_file(self, data, name):
        return ContentFile(base64.b64decode(data), name=name)
