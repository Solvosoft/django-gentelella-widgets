"""Upload tokens outside the form widgets: the DRF fields, the digital
signature serializer and the render endpoint take only a finished upload of
who presents the token."""
import base64
import json

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, override_settings
from django.urls import reverse

from djgentelella.chunked_upload.constants import UPLOADING
from djgentelella.chunked_upload.utils import ANY_USER, find_upload, request_user
from djgentelella.fields.files import ChunkedFileField, DigitalSignatureField
from djgentelella.firmador_digital.signvalue_utils import ValueDSParser
from djgentelella.serializers.firmador_digital import InitialSignatureSerializer
from djgentelella.tests.UploadsHardening_Test import UploadsTestBase

#: Each test signs users in: a fast hasher keeps it from spending seconds
#: per test hashing their passwords (PBKDF2).
FAST_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


def b64(data):
    return base64.b64encode(json.dumps(data).encode()).decode()


class TokenTestBase(UploadsTestBase):
    def request(self, user):
        request = RequestFactory().get('/')
        request.user = user
        return request

    def read(self, uploaded):
        return uploaded.read() if uploaded else None


class FindUploadTests(TokenTestBase):
    def test_who_presents_the_token(self):
        upload = self.upload(self.owner)
        token = upload.upload_id
        self.assertEqual(find_upload(token, self.owner), upload)
        self.assertIsNone(find_upload(token, self.other))
        self.assertIsNone(find_upload(token, AnonymousUser()))
        self.assertIsNone(find_upload(token, None))
        self.assertEqual(find_upload(token, ANY_USER), upload)

    def test_an_anonymous_upload_is_for_anonymous_visitors(self):
        upload = self.upload(None)
        self.assertEqual(find_upload(upload.upload_id, AnonymousUser()), upload)
        self.assertEqual(find_upload(upload.upload_id, None), upload)
        self.assertIsNone(find_upload(upload.upload_id, self.owner))

    def test_an_unfinished_upload_is_never_taken(self):
        upload = self.upload(self.owner, status=UPLOADING)
        self.assertIsNone(find_upload(upload.upload_id, self.owner))
        self.assertIsNone(find_upload(upload.upload_id, ANY_USER))

    def test_what_is_not_a_token(self):
        for token in (None, '', 3, {'token': 'x'}, ['x']):
            self.assertIsNone(find_upload(token, ANY_USER))

    def test_request_user(self):
        self.assertIs(request_user({'request': self.request(self.owner)}), self.owner)
        self.assertIs(request_user({'user': self.other}), self.other)
        self.assertIsNone(request_user({'user': None}))
        self.assertIs(request_user({}), ANY_USER)
        self.assertIs(request_user(None), ANY_USER)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class ChunkedFileFieldTests(TokenTestBase):
    def value(self, upload, context):
        field = ChunkedFileField()
        field._context = context
        return self.read(field.to_internal_value(
            json.dumps({'token': upload.upload_id})))

    def test_the_owner_attaches_the_upload(self):
        upload = self.upload(self.owner)
        self.assertEqual(self.value(upload, {'request': self.request(self.owner)}),
                         b'data')

    def test_the_token_of_another_user_attaches_nothing(self):
        upload = self.upload(self.owner)
        self.assertIsNone(self.value(upload, {'request': self.request(self.other)}))
        anonymous = self.request(AnonymousUser())
        self.assertIsNone(self.value(upload, {'request': anonymous}))

    def test_an_unfinished_upload_attaches_nothing(self):
        upload = self.upload(self.owner, status=UPLOADING)
        self.assertIsNone(self.value(upload, {'request': self.request(self.owner)}))

    def test_without_a_request_the_token_is_enough(self):
        upload = self.upload(self.owner)
        self.assertEqual(self.value(upload, {}), b'data')


@override_settings(PASSWORD_HASHERS=FAST_HASHERS)
class DigitalSignatureFieldTests(TokenTestBase):
    def value(self, upload, context):
        field = DigitalSignatureField()
        field._context = context
        return self.read(field.to_internal_value(b64({'token': upload.upload_id})))

    def test_only_the_users_upload(self):
        upload = self.upload(self.owner)
        self.assertEqual(self.value(upload, {'request': self.request(self.owner)}),
                         b'data')
        self.assertIsNone(self.value(upload, {'request': self.request(self.other)}))

    def test_the_form_widget_has_no_request(self):
        # DigitalSignatureInput reads the token through ValueDSParser: on
        # purpose, whoever uploaded it, as the generic upload widgets.
        upload = self.upload(self.owner)
        self.assertEqual(self.read(ValueDSParser().get_file_from_token(
            upload.upload_id)), b'data')
        unfinished = self.upload(self.owner, status=UPLOADING)
        self.assertIsNone(ValueDSParser().get_file_from_token(unfinished.upload_id))


class SignatureSerializerTests(TokenTestBase):
    """What the signing websocket reads: SignConsumer passes the user of the
    socket in the serializer's context."""

    def document(self, upload, user):
        content = {
            'action': 'initial_signature', 'socket_id': 's',
            'docsettings': {},
            'card': {key: 'x' for key in ('certificate', 'commonName', 'firstName',
                                          'identification', 'lastName',
                                          'tokenSerialNumber')},
            'instance': {'pk': self.owner.pk,
                         'cc': ContentType.objects.get_for_model(User).pk,
                         'value': b64({'token': upload.upload_id})},
        }
        serializer = InitialSignatureSerializer(data=content, context={'user': user})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.validated_data['instance']['value']

    def test_only_the_document_of_the_signer(self):
        upload = self.upload(self.owner)
        self.assertEqual(self.document(upload, self.owner), b'data')
        self.assertIsNone(self.document(upload, self.other))
        self.assertIsNone(self.document(upload, None))


class RenderEndpointTests(TokenTestBase):
    def get(self, upload, user, status=200):
        self.client.force_login(user)
        url = reverse('digital_signature_file_api',
                      args=[ContentType.objects.get_for_model(User).pk, self.owner.pk])
        response = self.client.get(url, {'value': b64({'token': upload.upload_id})})
        self.assertEqual(response.status_code, status)
        return b''.join(response) if response.streaming else response.content

    def test_only_who_uploaded_it_sees_the_document(self):
        upload = self.upload(self.owner)
        self.assertEqual(self.get(upload, self.owner), b'data')
        # Not found, as a token of no upload.
        self.get(upload, self.other, status=404)
        self.get(self.upload(self.owner, status=UPLOADING), self.owner, status=404)
