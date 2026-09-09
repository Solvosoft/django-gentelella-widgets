import base64
import io
import logging

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from requests import HTTPError, Timeout, RequestException
from requests.exceptions import JSONDecodeError

from djgentelella.firmador_digital.models import UserSignatureConfig
from djgentelella.models import ChunkedUpload

logger = logging.getLogger(__name__)


class RemoteSignerClient:
    def __init__(self, user):
        self.user = user

    def load_settings(self, docsettings):
        sc = UserSignatureConfig.objects.filter(user=self.user).first()
        settings = {}
        if sc:
            settings.update(sc.config)
        settings.update(docsettings)
        return settings

    def load_certificate(self, certtoken):
        return certtoken['certificate']

    def get_b64document(self, value):

        return base64.b64encode(value).decode()

    def send_document_to_sign(self, instance, usertoken, docsettings):
        b64doc = self.get_b64document(instance['value'])

        files = {
            'b64Document': b64doc,
            'DocumentExtension': '.pdf',
            'settings': self.load_settings(docsettings),
            'certToken': self.load_certificate(usertoken),
        }

        try:
            response = requests.post(settings.FIRMADOR_SIGN_URL, json=files)
            return response.json()
        except JSONDecodeError as errj:
            try:
                data = response.json(strict=False)
            except JSONDecodeError:
                logger.error(
                    'Invalid JSON from signing service: %s -- body: %.500s',
                    str(errj), response.text, exc_info=errj
                )
                return self.get_error_response(
                    _('The signing service returned an invalid response.'),
                    response.text[:500], 502, 2
                )
            logger.warning(
                'Signing service answered with a stray control character '
                '(likely an unescaped stacktrace); recovered its message: %s',
                data.get('error') or data.get('detail')
            )
            message = data.get('error') or data.get('detail') or str(errj)
            return self.get_error_response(message, message, response.status_code, 0)
        except ConnectionError as errc:
            logger.error(
                'ConnectionError sending document to sign: %s', str(errc), exc_info=errc
            )
            error_msg = _('Unable to connect to the signing service.')
            return self.get_error_response(error_msg, str(errc), 503, 2)
        except Timeout as errt:
            logger.error(
                'Timeout sending document to sign: %s', str(errt), exc_info=errt
            )
            error_msg = _('The request to the signing service timed out.')
            return self.get_error_response(error_msg, str(errt), 408, 12)
        except RequestException as errr:
            logger.error(
                'RequestException sending document to sign: %s', str(errr), exc_info=errr
            )
            error_msg = _(
                'An exception occurred in the request to the signing service.'
            )
            return self.get_error_response(error_msg, str(errr), 500, 999)

    def validate_document(self, instance):
        b64doc = self.get_b64document(instance['value'])
        files = {
            'b64Document': b64doc,
            'DocumentExtension': '.pdf',
        }
        response = requests.post(
            settings.FIRMADOR_VALIDA_URL, json=files
        )
        return response.json()

    def _finalize_signature(self, data_to_sign, task):
        result = None
        error_msg = _('An unexpected error occurred during the signing process.')

        try:
            logger.info('Sending request to signing service')
            response = requests.post(settings.FIRMADOR_SIGN_COMPLETE, json=data_to_sign)
            response.raise_for_status()
            logger.info('Successfully finalized signature for the task.')
            result = response.json()
        except HTTPError as errh:
            logger.error(
                'HTTPError during signature finalization for task %s: %s',
                task,
                str(errh),
                exc_info=errh
            )
            error_msg = _(
                'An error occurred while communicating with the signing service.'
            )
            result = self.get_error_response(error_msg, str(errh), 502, 2)

        except ConnectionError as errc:
            logger.error(
                'ConnectionError during signature finalization for task %s: %s',
                task,
                str(errc),
                exc_info=errc
            )
            error_msg = _('Unable to connect to the signing service.')
            result = self.get_error_response(error_msg, str(errc), 503, 2)
        except Timeout as errt:
            logger.error(
                'Timeout during signature finalization for task %s: %s',
                task,
                str(errt),
                exc_info=errt
            )
            error_msg = _('The request to the signing service timed out.')
            result = self.get_error_response(error_msg, str(errt), 408, 12)
        except RequestException as errr:
            logger.error(
                'RequestException during signature finalization for task %s: %s',
                task,
                str(errr),
                exc_info=errr
            )
            error_msg = _('An exception ocurred el request to the signing service.')
            result = self.get_error_response(error_msg, str(errr), 500, 999)
        except Exception as erre:
            logger.error(
                'Exception during signature finalization for task %s: %s',
                task,
                str(erre),
                exc_info=erre
            )
            error_msg = _('An unexpected error occurred during the signing process.')
            result = self.get_error_response(error_msg, str(erre), 500, 999)

        return result

    def get_error_response(self, error_msg, details, status, code):
        return {
            'result': False,
            'error': str(error_msg),
            'details': details,
            'status': status,
            'code': code,
        }

    def complete_signature(self, data_to_sign):
        datatosign = {
            'signature': data_to_sign['signature'],
            'documentid': data_to_sign['documentid'],
            'certificate': data_to_sign['certificate'],
        }

        instance = data_to_sign['instance']
        doc_info = self._finalize_signature(datatosign, instance)

        if doc_info:
            name = '%s_%s_%s.pdf' % (
                instance['pk'],
                self.user.pk,
                now().strftime('%m%d%Y'),
            )
            chunk = self.convert_to_django_file(
                doc_info['bytes'],
                name,
            )
            chfile = ChunkedUpload.objects.create(
                filename=name,
                file=ContentFile(b'', name=name),
                completed_on=now(),
                created_on=now(),
                user=self.user,
                status=2  # this is complete, but I can import constants here
            )
            chfile.append_chunk(chunk, save=True)
            return chfile.upload_id
        return False

    def convert_to_django_file(self, data, name):
        return io.BytesIO(base64.b64decode(data))
