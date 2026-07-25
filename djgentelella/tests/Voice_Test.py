import builtins
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from djgentelella.voice.views import _extract_text


def without_module(name):
    """Make ``import <name>`` raise, so a test can stand in for the extra not
    being installed while everything else still imports normally."""
    real_import = builtins.__import__

    def fake_import(module, *args, **kwargs):
        if module == name:
            raise ImportError('No module named %r' % name)
        return real_import(module, *args, **kwargs)

    return mock.patch('builtins.__import__', side_effect=fake_import)


class VoiceTranscribeTestCase(TestCase):
    """Both ASR backends are optional installs.

    Neither extra may be needed to import djgentelella or to reach the
    endpoint: a missing one has to surface as a 501 naming the extra to
    install, never as an import error at startup.
    """

    def setUp(self):
        self.url = reverse('voice-transcribe')
        self.user = get_user_model().objects.create_user(
            username='dictator', password='dictating')
        self.client.force_login(self.user)

    def test_an_anonymous_request_never_reaches_the_backend(self):
        # transcription costs cpu or money, so it is not open to the world
        self.client.logout()
        with mock.patch('djgentelella.voice.asr.transcribe') as transcribe:
            response = self.post()

        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response['Location'])
        self.assertFalse(transcribe.called)

    def post(self, **extra):
        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        return self.client.post(self.url, dict(file=audio, **extra))

    def test_a_request_without_audio_is_rejected(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)

    @override_settings(GENTELELLA_ASR_BACKEND='local')
    def test_local_without_the_asr_extra_reports_which_one_to_install(self):
        with mock.patch('djgentelella.voice.asr.transcribe',
                        side_effect=ImportError('No module named onnx_asr')):
            response = self.post()

        self.assertEqual(response.status_code, 501)
        self.assertIn('djgentelella[asr]', response.json()['error'])

    @override_settings(GENTELELLA_ASR_BACKEND='local')
    def test_local_returns_the_transcription(self):
        with mock.patch('djgentelella.voice.asr.transcribe',
                        return_value='hola mundo') as transcribe:
            response = self.post(language='es')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'text': 'hola mundo'})
        self.assertEqual(transcribe.call_args.kwargs['language'], 'es')

    @override_settings(GENTELELLA_ASR_BACKEND='local')
    def test_a_failing_transcription_does_not_leak_the_exception(self):
        with mock.patch('djgentelella.voice.asr.transcribe',
                        side_effect=RuntimeError('model exploded')):
            response = self.post()

        self.assertEqual(response.status_code, 500)
        self.assertNotIn('model exploded', response.json()['error'])

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL='http://asr.example/api')
    def test_remote_without_the_asr_remote_extra_reports_which_one(self):
        with without_module('requests'):
            response = self.post()

        self.assertEqual(response.status_code, 501)
        self.assertIn('djgentelella[asr-remote]', response.json()['error'])

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL='')
    def test_remote_without_a_url_is_a_configuration_error(self):
        response = self.post()

        self.assertEqual(response.status_code, 500)
        self.assertIn('GENTELELLA_ASR_REMOTE_URL', response.json()['error'])

    def test_the_backend_defaults_to_remote_only_when_a_url_is_set(self):
        # With no backend named, the presence of a remote url decides. Both are
        # usually read from the environment, so '' has to mean the same as unset
        # (an env var that is merely defined must not pick the backend).
        for unset in ('', None):
            with override_settings(GENTELELLA_ASR_BACKEND=unset,
                                   GENTELELLA_ASR_REMOTE_URL=unset):
                with mock.patch('djgentelella.voice.asr.transcribe',
                                return_value='local wins') as transcribe:
                    self.assertEqual(self.post().json(), {'text': 'local wins'})
                self.assertTrue(transcribe.called)

            with override_settings(GENTELELLA_ASR_BACKEND=unset,
                                   GENTELELLA_ASR_REMOTE_URL='http://asr.here'):
                with mock.patch('djgentelella.voice.asr.transcribe') as transcribe:
                    with without_module('requests'):
                        self.assertEqual(self.post().status_code, 501)
                self.assertFalse(transcribe.called)


class ExtractTextTestCase(TestCase):
    """The remote answer is normalized to a plain string."""

    def test_reads_both_shapes_and_never_returns_none(self):
        self.assertEqual(_extract_text({'text': 'flat'}), 'flat')
        self.assertEqual(
            _extract_text({'transcription': {'text': 'nested'}}), 'nested')
        self.assertEqual(_extract_text({'text': None}), '')
        self.assertEqual(_extract_text({}), '')
        self.assertEqual(_extract_text('not a dict'), '')
