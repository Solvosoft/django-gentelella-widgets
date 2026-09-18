from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from djgentelella.firmador_digital.utils import (
    RemoteSignerClient,
    firmador_headers,
    signer_complete_url,
)


def _response(payload):
    response = mock.Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class FirmadorHeadersTest(SimpleTestCase):
    """firmador_api answers 401 without its Bearer token; the header is opt-in."""

    @override_settings(FIRMADOR_TOKEN=None)
    def test_no_token_sends_no_authorization(self):
        self.assertEqual(firmador_headers(), {})

    @override_settings(FIRMADOR_TOKEN='')
    def test_empty_token_sends_no_authorization(self):
        # An empty value is "not configured", not "authenticate with nothing".
        self.assertEqual(firmador_headers(), {})

    @override_settings(FIRMADOR_TOKEN='s3cret')
    def test_token_becomes_bearer(self):
        self.assertEqual(firmador_headers(), {'Authorization': 'Bearer s3cret'})

    def test_unset_setting_sends_no_authorization(self):
        with self.settings():
            if hasattr(settings, 'FIRMADOR_TOKEN'):
                del settings.FIRMADOR_TOKEN
            self.assertEqual(firmador_headers(), {})


@override_settings(
    FIRMADOR_TOKEN='s3cret',
    FIRMADOR_SIGN_URL='http://firmador/firma/firme',
    FIRMADOR_VALIDA_URL='http://firmador/valida/',
    FIRMADOR_SIGN_COMPLETE='http://firmador/firma/completa',
)
class RemoteSignerClientAuthTest(SimpleTestCase):
    """Every call to the signer must carry the token, or that step gets a 401."""

    def setUp(self):
        self.client_ = RemoteSignerClient(user=mock.Mock(pk=1))

    def assert_bearer(self, post):
        self.assertEqual(
            post.call_args.kwargs['headers'], {'Authorization': 'Bearer s3cret'}
        )

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_sign_sends_token(self, post):
        post.return_value = _response({'documentid': 'x'})
        with mock.patch.object(RemoteSignerClient, 'load_settings', return_value={}):
            self.client_.send_document_to_sign(
                {'value': b'%PDF'}, {'certificate': 'c'}, {}
            )
        self.assertEqual(post.call_args.args[0], 'http://firmador/firma/firme')
        self.assert_bearer(post)

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_validate_sends_token(self, post):
        post.return_value = _response({'result': True})
        self.client_.validate_document({'value': b'%PDF'})
        self.assertEqual(post.call_args.args[0], 'http://firmador/valida/')
        self.assert_bearer(post)

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_complete_sends_token(self, post):
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'x'}, task='t')
        self.assertEqual(post.call_args.args[0], 'http://firmador/firma/completa')
        self.assert_bearer(post)


INSTANCE = 'http://a1b2c3d4e5f6:9999'
SERVICE_COMPLETE = 'http://firmador:9999/firma/completa'

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                      'LOCATION': 'firmador-affinity-tests'}}


@override_settings(
    CACHES=LOCMEM,
    FIRMADOR_TOKEN='s3cret',
    FIRMADOR_SIGN_URL='http://firmador:9999/firma/firme',
    FIRMADOR_SIGN_COMPLETE='http://firmador:9999/firma/completa',
)
class SignerAffinityTest(SimpleTestCase):
    """firmador_api keeps the document in memory: complete on the same replica."""

    def setUp(self):
        cache.clear()
        self.client_ = RemoteSignerClient(user=mock.Mock(pk=1))

    def _sign(self, post, answer):
        post.return_value = _response(answer)
        with mock.patch.object(RemoteSignerClient, 'load_settings', return_value={}):
            self.client_.send_document_to_sign(
                {'value': b'%PDF'}, {'certificate': 'c'}, {})

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_complete_goes_to_the_instance_that_signed(self, post):
        self._sign(post, {'documentid': 'd1', 'hostname': INSTANCE})
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'd1'}, task='t')
        self.assertEqual(post.call_args.args[0], INSTANCE + '/firma/completa')
        self.assertEqual(post.call_args.kwargs['headers'],
                         {'Authorization': 'Bearer s3cret'})

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_affinity_is_forgotten_after_completing(self, post):
        self._sign(post, {'documentid': 'd1', 'hostname': INSTANCE})
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'd1'}, task='t')
        self.assertEqual(signer_complete_url('d1'), SERVICE_COMPLETE)

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_non_distributed_signer_uses_the_service_url(self, post):
        self._sign(post, {'documentid': 'd1', 'hostname': 'localhost'})
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'd1'}, task='t')
        self.assertEqual(post.call_args.args[0], 'http://firmador:9999/firma/completa')

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_malformed_instance_url_is_ignored(self, post):
        for bad in ('http://evil.example/steal?x=', 'file:///etc/passwd',
                    'http://host:9999/../x', 'ftp://host'):
            self._sign(post, {'documentid': 'd1', 'hostname': bad})
            post.return_value = _response({'bytes': ''})
            self.client_._finalize_signature({'documentid': 'd1'}, task='t')
            self.assertEqual(post.call_args.args[0],
                             'http://firmador:9999/firma/completa', bad)

    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_unknown_document_uses_the_service_url(self, post):
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'never-signed'}, task='t')
        self.assertEqual(post.call_args.args[0], 'http://firmador:9999/firma/completa')

    @override_settings(FIRMADOR_AFFINITY=False)
    @mock.patch('djgentelella.firmador_digital.utils.requests.post')
    def test_affinity_can_be_disabled(self, post):
        self._sign(post, {'documentid': 'd1', 'hostname': INSTANCE})
        post.return_value = _response({'bytes': ''})
        self.client_._finalize_signature({'documentid': 'd1'}, task='t')
        self.assertEqual(post.call_args.args[0], 'http://firmador:9999/firma/completa')
