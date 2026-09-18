import base64
import io
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from requests import HTTPError, Timeout, RequestException
from requests.exceptions import JSONDecodeError

from djgentelella.firmador_digital.models import UserSignatureConfig
from djgentelella.models import ChunkedUpload

logger = logging.getLogger(__name__)


def firmador_headers():
    """
    Headers for every request to the signing service.

    firmador_api protects its endpoints with a Bearer token (API_TOKEN) and
    answers 401 without it. The token is optional here so projects that talk
    to an unprotected signer keep working unchanged: when FIRMADOR_TOKEN is
    unset or empty, no Authorization header is sent at all.
    """
    token = getattr(settings, 'FIRMADOR_TOKEN', None)
    if not token:
        return {}
    return {'Authorization': 'Bearer %s' % token}


# -- instance affinity ---------------------------------------------------------
# firmador_api keeps each document IN MEMORY between `firme` and `completa`.
# With several replicas behind one service name, `completa` has to reach the
# very instance that answered `firme`, or it finds nothing to complete. In
# distributed mode (IS_DISTRIBUTED=true) `firme` answers with that instance's
# own base URL in `hostname`; it is kept here, server side, keyed by the
# document id. It never travels through the browser: a URL the client could
# rewrite would make the server post the signature -- and the Bearer token --
# wherever it was told to.
AFFINITY_CACHE_PREFIX = 'djgentelella:firmador:instance:'
_INSTANCE_URL = re.compile(r'^https?://[A-Za-z0-9._-]+(:[0-9]{1,5})?$')


def _affinity_key(documentid):
    return '%s%s' % (AFFINITY_CACHE_PREFIX, documentid)


def remember_signer_instance(signed_request):
    """Store the instance URL returned by `firme`, if the signer sent one."""
    if not getattr(settings, 'FIRMADOR_AFFINITY', True):
        return
    if not isinstance(signed_request, dict):
        return
    documentid = signed_request.get('documentid')
    hostname = signed_request.get('hostname') or ''
    if not documentid or not _INSTANCE_URL.match(hostname):
        # Not distributed ("localhost" or nothing): the service URL is fine.
        return
    cache.set(_affinity_key(documentid), hostname,
              getattr(settings, 'FIRMADOR_AFFINITY_TTL', 3600))


def signer_complete_url(documentid):
    """URL to complete `documentid`: its instance's, or the service one."""
    instance = cache.get(_affinity_key(documentid)) if documentid else None
    if instance and _INSTANCE_URL.match(instance):
        return instance.rstrip('/') + '/firma/completa'
    return settings.FIRMADOR_SIGN_COMPLETE


def forget_signer_instance(documentid):
    if documentid:
        cache.delete(_affinity_key(documentid))


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
            response = requests.post(
                settings.FIRMADOR_SIGN_URL, json=files, headers=firmador_headers()
            )
            data = response.json()
            remember_signer_instance(data)
            return data
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
                'RequestException sending document to sign: %s',
                str(errr),
                exc_info=errr,
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
            settings.FIRMADOR_VALIDA_URL, json=files, headers=firmador_headers()
        )
        return response.json()

    def _finalize_signature(self, data_to_sign, task):
        result = None
        error_msg = _('An unexpected error occurred during the signing process.')

        try:
            logger.info('Sending request to signing service')
            response = requests.post(
                signer_complete_url(data_to_sign.get('documentid')),
                json=data_to_sign,
                headers=firmador_headers(),
            )
            response.raise_for_status()
            forget_signer_instance(data_to_sign.get('documentid'))
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
