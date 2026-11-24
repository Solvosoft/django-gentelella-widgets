"""
The digital signature only reads the file the server named, and only for a
user allowed to use it (W15).

Before, the preview endpoint, the signing websocket and the form took
``{contenttype, pk, field_name}`` from the client: any signed-in user saw or
signed the file of any object. The ``*Forged*`` tests are that reproduction.
"""
import base64
import json
from unittest import mock

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from rest_framework import serializers

from demoapp.models import DigitalSignature
from djgentelella.fields.files import DigitalSignatureField
from djgentelella.firmador_digital import access
from djgentelella.firmador_digital.consumers.sign import SignConsumer
from djgentelella.firmador_digital.viewsets import DigitalSignatureRenderFileAPIView
from djgentelella.serializers.firmador_digital import InitialSignatureSerializer
from djgentelella.widgets.digital_signature import DigitalSignatureInput

PDF = b'%PDF-1.4 secret'
HOOK = 'djgentelella.tests.FirmadorAccess_Test.only_alice'
CALLS = []


def only_alice(user, instance, field_name, action):
    """A project rule: only ``alice``, whatever her permissions."""
    CALLS.append((user.username if user else None, instance, field_name, action))
    return user is not None and user.username == 'alice'


def b64(data):
    return base64.b64encode(json.dumps(data).encode()).decode()


def tamper(reference, **changes):
    """The payload of a signed reference changed, keeping its signature."""
    payload, rest = reference.split(':', 1)
    data = json.loads(signing.b64_decode(payload.encode()))
    data.update(changes)
    return signing.b64_encode(json.dumps(data, separators=(',', ':')).encode()
                              ).decode() + ':' + rest


class FirmadorAccessBase(TestCase):
    def setUp(self):
        self.cc = ContentType.objects.get_for_model(DigitalSignature).pk
        self.doc = self.document('mine.pdf', PDF)
        self.other_doc = self.document('other.pdf', b'%PDF-1.4 other')
        self.intruder = User.objects.create_user('intruder')
        self.viewer = self.user('viewer', 'view_digitalsignature')
        self.editor = self.user('editor', 'change_digitalsignature')
        self.alice = User.objects.create_user('alice')
        self.reference = access.sign_document_reference(self.doc, 'file')
        self.forged = b64({'contenttype': self.cc, 'pk': self.doc.pk,
                           'field_name': 'file'})
        CALLS.clear()

    def document(self, name, content):
        doc = DigitalSignature(filename=name)
        doc.file.save(name, ContentFile(content), save=True)
        self.addCleanup(doc.file.delete, save=False)
        return doc

    def user(self, username, codename):
        user = User.objects.create_user(username)
        user.user_permissions.add(Permission.objects.get(
            codename=codename, content_type_id=self.cc))
        return User.objects.get(pk=user.pk)


class ReferenceTests(FirmadorAccessBase):
    def test_round_trip(self):
        self.assertEqual(access.load_document_reference(self.reference),
                         {'contenttype': self.cc, 'pk': self.doc.pk,
                          'field_name': 'file'})

    def test_what_is_not_a_signed_reference(self):
        for value in (self.forged, b64({'field_name': 'file'}), '', None, 'x:y',
                      tamper(self.reference, pk=self.other_doc.pk),
                      tamper(self.reference, contenttype=self.cc + 1),
                      tamper(self.reference, field_name='filename'),
                      # The same payload signed with another salt.
                      signing.dumps({'contenttype': self.cc, 'pk': self.doc.pk,
                                     'field_name': 'file'})):
            with self.subTest(value=value):
                self.assertIsNone(access.load_document_reference(value))
                self.assertIsNone(access.decode_document_value(value))

    def test_a_token_needs_no_signature(self):
        self.assertEqual(access.decode_document_value(b64({'token': 'abc'})),
                         {'token': 'abc'})
        # Not a way to smuggle a reference next to a token.
        self.assertEqual(access.decode_document_value(
            b64({'token': 'abc', 'field_name': 'file', 'pk': 1})),
            {'token': 'abc'})

    @override_settings(FIRMADOR_REFERENCE_MAX_AGE=60)
    def test_max_age(self):
        self.assertIsNotNone(access.load_document_reference(self.reference))
        with mock.patch('django.core.signing.time.time',
                        return_value=signing.time.time() + 61):
            self.assertIsNone(access.load_document_reference(self.reference))

    def test_default_rule(self):
        for user, action, allowed in (
                (self.intruder, access.VIEW, False),
                (self.intruder, access.SIGN, False),
                (self.viewer, access.VIEW, True),
                (self.viewer, access.SIGN, False),
                (self.editor, access.VIEW, True),
                (self.editor, access.SIGN, True),
                (None, access.VIEW, False)):
            with self.subTest(user=user, action=action):
                self.assertEqual(access.has_document_access(
                    user, self.doc, 'file', action), allowed)

    def test_an_inactive_editor(self):
        self.editor.is_active = False
        self.editor.save()
        self.assertFalse(access.has_document_access(
            User.objects.get(pk=self.editor.pk), self.doc, 'file', access.SIGN))

    @override_settings(FIRMADOR_ACCESS_CHECK=HOOK)
    def test_the_project_rule_replaces_the_default(self):
        self.assertTrue(access.has_document_access(
            self.alice, self.doc, 'file', access.SIGN))
        self.assertFalse(access.has_document_access(
            self.editor, self.doc, 'file', access.SIGN))
        self.assertEqual(CALLS[0], ('alice', self.doc, 'file', access.SIGN))


class RenderEndpointTests(FirmadorAccessBase):
    def get(self, user, value, doc=None):
        if user is not None:
            self.client.force_login(user)
        doc = doc or self.doc
        url = reverse('digital_signature_file_api', args=[self.cc, doc.pk])
        return self.client.get(url, {'value': value})

    def test_forged_reference_is_rejected(self):
        # The reproduction: 200 and the PDF before W15, for anyone.
        for user in (self.intruder, self.editor):
            with self.subTest(user=user):
                response = self.get(user, self.forged)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(PDF, response.content)

    def test_forged_field_name_alone_is_rejected(self):
        # The view used to take the object from the URL.
        self.assertEqual(self.get(self.editor, b64({'field_name': 'file'})
                                  ).status_code, 404)

    def test_tampered_reference_is_rejected(self):
        for value in (tamper(self.reference, pk=self.other_doc.pk),
                      tamper(self.reference, contenttype=self.cc + 1),
                      tamper(self.reference, field_name='filename')):
            with self.subTest(value=value):
                self.assertEqual(self.get(self.editor, value).status_code, 404)

    def test_a_reference_for_another_object_than_the_url(self):
        self.assertEqual(self.get(self.editor, self.reference,
                                  doc=self.other_doc).status_code, 404)

    def test_who_may_see_it(self):
        self.assertEqual(self.get(self.intruder, self.reference).status_code, 404)
        for user in (self.viewer, self.editor):
            with self.subTest(user=user):
                response = self.get(user, self.reference)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, PDF)

    def test_anonymous_is_sent_to_log_in(self):
        self.assertEqual(self.get(None, self.reference).status_code, 302)

    def test_no_permission_and_no_object_look_the_same(self):
        denied = self.get(self.intruder, self.reference)
        gone = access.sign_document_reference(self.other_doc, 'file')
        url = reverse('digital_signature_file_api',
                      args=[self.cc, self.other_doc.pk])
        self.other_doc.delete()
        self.client.force_login(self.editor)
        missing = self.client.get(url, {'value': gone})
        self.assertEqual((denied.status_code, denied.content),
                         (missing.status_code, missing.content))

    @override_settings(FIRMADOR_ACCESS_CHECK=HOOK)
    def test_the_project_rule(self):
        self.assertEqual(self.get(self.alice, self.reference).status_code, 200)
        self.assertEqual(self.get(self.editor, self.reference).status_code, 404)
        self.assertIn(('alice', self.doc, 'file', access.VIEW), CALLS)

    def test_check_user_of_a_subclass(self):
        class OnlyEditor(DigitalSignatureRenderFileAPIView):
            def check_user(self, cc, pk, user, token=None):
                return user.username == 'editor'

        def get(user):
            request = RequestFactory().get('/', {'value': self.reference})
            request.user = user
            return OnlyEditor.as_view()(request, cc=self.cc, pk=self.doc.pk)

        self.assertEqual(get(self.editor).status_code, 200)
        self.assertEqual(get(self.viewer).status_code, 404)

    def test_the_message_is_translated(self):
        view = DigitalSignatureRenderFileAPIView()
        with translation.override('es'):
            self.assertEqual(str(view.not_found().data['detail']),
                             'Archivo no encontrado')


class SignSerializerTests(FirmadorAccessBase):
    """What the signing websocket validates, with its user in the context."""

    def serializer(self, user, value, doc=None, action=access.SIGN):
        doc = doc or self.doc
        content = {
            'action': 'initial_signature', 'socket_id': 's', 'docsettings': {},
            'card': {key: 'x' for key in ('certificate', 'commonName', 'firstName',
                                          'identification', 'lastName',
                                          'tokenSerialNumber')},
            'instance': {'pk': doc.pk, 'cc': self.cc, 'value': value},
        }
        serializer = InitialSignatureSerializer(
            data=content, context={'user': user, 'action': action})
        serializer.is_valid()
        return serializer

    def assert_rejected(self, serializer, message):
        self.assertFalse(serializer.is_valid())
        self.assertIn(message, str(serializer.errors['instance']))

    def test_forged_reference_is_rejected(self):
        # The reproduction: the serializer read the file of any object.
        with translation.override('en'):
            self.assert_rejected(self.serializer(self.editor, self.forged),
                                 'Invalid encode value')

    def test_tampered_reference_is_rejected(self):
        with translation.override('en'):
            for value in (tamper(self.reference, pk=self.other_doc.pk),
                          tamper(self.reference, field_name='filename')):
                with self.subTest(value=value):
                    self.assert_rejected(self.serializer(self.editor, value),
                                         'Invalid encode value')
            # Signed, but for another cc/pk than the one sent next to it.
            self.assert_rejected(
                self.serializer(self.editor, self.reference, doc=self.other_doc),
                'The document is not available.')

    def test_who_may_sign_it(self):
        with translation.override('en'):
            for user in (self.intruder, self.viewer, None):
                with self.subTest(user=user):
                    self.assert_rejected(self.serializer(user, self.reference),
                                         'The document is not available.')
        serializer = self.serializer(self.editor, self.reference)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['instance']['value'], PDF)

    def test_without_a_user_in_the_context(self):
        serializer = InitialSignatureSerializer(data=self.serializer(
            self.editor, self.reference).initial_data)
        self.assertFalse(serializer.is_valid())

    def test_no_permission_and_no_object_look_the_same(self):
        denied = self.serializer(self.intruder, self.reference).errors
        gone = access.sign_document_reference(self.other_doc, 'file')
        gone_doc = DigitalSignature(pk=self.other_doc.pk)
        self.other_doc.delete()
        missing = self.serializer(self.editor, gone, doc=gone_doc).errors
        self.assertEqual(denied, missing)

    @override_settings(FIRMADOR_ACCESS_CHECK=HOOK)
    def test_the_project_rule(self):
        self.assertTrue(self.serializer(self.alice, self.reference).is_valid())
        self.assertFalse(self.serializer(self.editor, self.reference).is_valid())

    def test_the_messages_are_translated(self):
        with translation.override('es'):
            self.assert_rejected(self.serializer(self.editor, self.forged),
                                 'Valor codificado inválido')
            self.assert_rejected(self.serializer(self.intruder, self.reference),
                                 'El documento no está disponible.')


class SignConsumerTests(FirmadorAccessBase):
    """The consumer itself, with the signer mocked: what reaches it."""

    def receive(self, user, value, action='initial_signature'):
        consumer = SignConsumer()
        consumer.scope = {'type': 'websocket', 'user': user}
        consumer.send_json = mock.Mock()
        content = {
            'action': action, 'socket_id': 's', 'docsettings': {},
            'logo_url': None,
            'card': {key: 'x' for key in ('certificate', 'commonName', 'firstName',
                                          'identification', 'lastName',
                                          'tokenSerialNumber')},
            'instance': {'pk': self.doc.pk, 'cc': self.cc, 'value': value},
        }
        target = ('validate_document' if action == 'validate_document'
                  else 'send_document_to_sign')
        with mock.patch('djgentelella.firmador_digital.consumers.sign.'
                        'RemoteSignerClient.' + target,
                        return_value={'result': True}) as signer:
            consumer.receive_json(content)
        return signer, consumer.send_json.call_args.args[0]

    def test_forged_reference_never_reaches_the_signer(self):
        signer, answer = self.receive(self.editor, self.forged)
        signer.assert_not_called()
        self.assertEqual((answer['result'], answer['status']), (False, 400))

    def test_tampered_reference_never_reaches_the_signer(self):
        signer, answer = self.receive(
            self.editor, tamper(self.reference, pk=self.other_doc.pk))
        signer.assert_not_called()
        self.assertEqual(answer['status'], 400)

    def test_without_permission(self):
        for user in (self.intruder, self.viewer):
            with self.subTest(user=user):
                signer, answer = self.receive(user, self.reference)
                signer.assert_not_called()
                self.assertEqual(answer['status'], 400)

    def test_the_editor_signs(self):
        signer, answer = self.receive(self.editor, self.reference)
        self.assertEqual(signer.call_args.kwargs['instance']['value'], PDF)
        self.assertEqual(answer['socket_id'], 's')

    def test_validating_needs_view(self):
        signer, answer = self.receive(self.viewer, self.reference,
                                      action='validate_document')
        self.assertEqual(signer.call_args.kwargs['instance']['value'], PDF)
        signer, answer = self.receive(self.intruder, self.reference,
                                      action='validate_document')
        signer.assert_not_called()

    @override_settings(FIRMADOR_ACCESS_CHECK=HOOK)
    def test_the_project_rule(self):
        signer, answer = self.receive(self.alice, self.reference)
        signer.assert_called_once()
        self.assertIn(('alice', self.doc, 'file', access.SIGN), CALLS)


class FormTests(FirmadorAccessBase):
    def test_the_widget_renders_a_signed_reference(self):
        widget = DigitalSignatureInput(render_basename='digital_signature_file_api')
        attrs = widget.get_context('file', self.doc.file, {'id': 'id_file'}
                                   )['widget']['attrs']
        self.assertEqual(access.load_document_reference(attrs['data-value']),
                         {'contenttype': self.cc, 'pk': self.doc.pk,
                          'field_name': 'file'})
        self.assertEqual(attrs['data-renderattr'], 'value=' + attrs['data-value'])

    def test_the_widget_takes_no_forged_reference(self):
        # The reproduction: the form attached the file of the forged object.
        widget = DigitalSignatureInput(render_basename='digital_signature_file_api')
        self.assertIsNone(widget.value_from_datadict(
            {'file': self.forged}, {}, 'file'))
        self.assertEqual(widget.value_from_datadict(
            {'file': self.reference}, {}, 'file').name, self.doc.file.name)

    def test_the_drf_field_takes_only_its_own_reference(self):
        class Serializer(serializers.ModelSerializer):
            file = DigitalSignatureField()

            class Meta:
                model = DigitalSignature
                fields = ['file']

        field = Serializer(instance=self.doc).fields['file']
        self.assertIsNone(field.to_internal_value(self.forged))
        self.assertEqual(field.to_internal_value(self.reference).name,
                         self.doc.file.name)
        self.assertIsNone(field.to_internal_value(
            access.sign_document_reference(self.other_doc, 'file')))
        self.assertIsNone(field.to_internal_value(
            access.sign_document_reference(self.doc, 'filename')))
