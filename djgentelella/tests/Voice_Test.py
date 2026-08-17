import array
import builtins
import io
import math
import unittest
import wave
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from djgentelella.voice import asr
from djgentelella.voice.views import _extract_text

try:                          # the `asr` extra; the endpoint works without it
    import av                 # noqa: F401
    import numpy              # noqa: F401
    HAS_DECODER = True
except ImportError:
    HAS_DECODER = False


def wav_bytes(seconds=0.25, rate=48000, freq=440.0):
    """A real mono 16-bit WAV, so the decoder is exercised end to end rather
    than against a mock that would hide the resampling."""
    samples = array.array('h', (
        int(20000 * math.sin(2 * math.pi * freq * i / rate))
        for i in range(int(rate * seconds))))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())
    return buffer.getvalue()


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

        # 403 json, not a redirect: the caller is the widget's fetch(), which
        # would follow a 302 and then fail parsing the login page as json
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('authentication', response.json()['error'])
        self.assertFalse(transcribe.called)

    def test_the_endpoint_the_package_publishes_is_the_one_that_is_gated(self):
        # the rest of this file exercises the demo route; this is the url
        # djgentelella.urls actually ships, and nothing else covers it
        url = reverse('voice_transcribe')
        self.assertNotEqual(url, self.url)

        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        self.client.logout()
        with mock.patch('djgentelella.voice.asr.transcribe') as transcribe:
            self.assertEqual(self.client.post(url, {'file': audio}).status_code,
                             403)
        self.assertFalse(transcribe.called)

        self.client.force_login(self.user)
        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        with override_settings(GENTELELLA_ASR_BACKEND='local'):
            with mock.patch('djgentelella.voice.asr.transcribe',
                            return_value='desde la libreria'):
                response = self.client.post(url, {'file': audio})
        self.assertEqual(response.json(), {'text': 'desde la libreria'})

    def post(self, **extra):
        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        return self.client.post(self.url, dict(file=audio, **extra))

    def test_a_request_without_audio_is_rejected(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)

    @override_settings(GENTELELLA_ASR_BACKEND='local')
    def test_local_without_the_asr_extra_reports_which_one_to_install(self):
        # what `import onnx_asr` actually raises when the extra is absent
        with mock.patch(
                'djgentelella.voice.asr.transcribe',
                side_effect=ModuleNotFoundError('No module named onnx_asr')):
            response = self.post()

        self.assertEqual(response.status_code, 501)
        self.assertIn('djgentelella[asr]', response.json()['error'])

    @override_settings(GENTELELLA_ASR_BACKEND='local')
    def test_a_broken_install_is_not_reported_as_a_missing_extra(self):
        # A wrong onnxruntime ABI raises ImportError, not ModuleNotFoundError.
        # Telling that operator to install the extra they already have sends
        # them down the wrong path, so it stays a plain server error.
        with mock.patch('djgentelella.voice.asr.transcribe',
                        side_effect=ImportError('undefined symbol: ...')):
            response = self.post()

        self.assertEqual(response.status_code, 500)

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

    @override_settings(GENTELELLA_ASR_BACKEND='Remote')
    def test_a_misspelled_backend_is_a_configuration_error(self):
        # Anything that is not exactly 'remote' used to fall through to the
        # local backend, which then tried to pull a 670 MB model and blamed a
        # missing extra -- pointing at the wrong backend entirely.
        with mock.patch('djgentelella.voice.asr.transcribe') as transcribe:
            with self.assertRaises(ImproperlyConfigured):
                self.post()
        self.assertFalse(transcribe.called)

    @override_settings(GENTELELLA_ASR_BACKEND='local',
                       GENTELELLA_ASR_MAX_UPLOAD_BYTES=4)
    def test_an_oversized_upload_never_reaches_the_backend(self):
        # Transcription burns cpu or money and holds a worker for up to
        # GENTELELLA_ASR_TIMEOUT seconds, so the size is checked up front.
        with mock.patch('djgentelella.voice.asr.transcribe') as transcribe:
            response = self.post()

        self.assertEqual(response.status_code, 413)
        self.assertFalse(transcribe.called)

    @override_settings(GENTELELLA_ASR_BACKEND='local',
                       GENTELELLA_ASR_MAX_UPLOAD_BYTES=None)
    def test_the_size_limit_can_be_disabled(self):
        with mock.patch('djgentelella.voice.asr.transcribe',
                        return_value='sin limite'):
            response = self.post()

        self.assertEqual(response.status_code, 200)


class RemoteBackendTestCase(TestCase):
    """What actually goes on the wire to the external ASR.

    Everything here is remapped by settings so one endpoint can talk to OpenAI,
    Groq, vLLM or Deepgram, which makes it the part most likely to be silently
    wrong against a given server.
    """

    URL = 'http://asr.example/v1/audio/transcriptions'

    def setUp(self):
        self.url = reverse('voice-transcribe')
        self.user = get_user_model().objects.create_user(
            username='dictator', password='dictating')
        self.client.force_login(self.user)

    def post(self, payload=None, status_code=200, **extra):
        """POST to the endpoint with requests.post mocked out, returning both
        the view response and the call the view made."""
        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        remote = mock.Mock(status_code=status_code)
        remote.json.return_value = payload if payload is not None else {
            'text': 'hola mundo'}
        with mock.patch('requests.post', return_value=remote) as post:
            response = self.client.post(self.url, dict(file=audio, **extra))
        return response, post

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_it_posts_the_audio_and_returns_the_transcription(self):
        response, post = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'text': 'hola mundo'})
        self.assertEqual(post.call_args.args[0], self.URL)
        name, handle, content_type = post.call_args.kwargs['files']['file']
        self.assertEqual(name, 'dictation.wav')
        self.assertEqual(content_type, 'audio/wav')

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_the_nested_transcription_shape_is_understood(self):
        response, _ = self.post(payload={'transcription': {'text': 'anidado'}})
        self.assertEqual(response.json(), {'text': 'anidado'})

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL,
                       GENTELELLA_ASR_REMOTE_TOKEN='s3cret')
    def test_the_token_travels_as_a_bearer_header(self):
        _, post = self.post()
        self.assertEqual(post.call_args.kwargs['headers'],
                         {'Authorization': 'Bearer s3cret'})

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL,
                       GENTELELLA_ASR_REMOTE_TOKEN='')
    def test_no_header_is_sent_without_a_token(self):
        # commonly read from the environment, where unset arrives as ''
        _, post = self.post()
        self.assertEqual(post.call_args.kwargs['headers'], {})

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL,
                       GENTELELLA_ASR_TIMEOUT=7)
    def test_the_timeout_is_honoured(self):
        # without it a hung ASR would pin a worker for as long as it takes
        _, post = self.post()
        self.assertEqual(post.call_args.kwargs['timeout'], 7)

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_the_model_is_omitted_until_configured(self):
        # some OpenAI-compatible servers serve a single model and reject `model`
        _, post = self.post()
        self.assertNotIn('model', post.call_args.kwargs['data'])

        with override_settings(GENTELELLA_ASR_REMOTE_MODEL='whisper-large-v3'):
            _, post = self.post()
        self.assertEqual(post.call_args.kwargs['data']['model'],
                         'whisper-large-v3')

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_the_language_is_forwarded(self):
        _, post = self.post(language='es')
        self.assertEqual(post.call_args.kwargs['data']['language'], 'es')

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_the_prompt_field_can_be_renamed_for_the_target_api(self):
        _, post = self.post(initial_prompt='terminos medicos')
        self.assertEqual(post.call_args.kwargs['data']['prompt'],
                         'terminos medicos')

        with override_settings(GENTELELLA_ASR_REMOTE_PROMPT_PARAM='context'):
            _, post = self.post(initial_prompt='terminos medicos')
        data = post.call_args.kwargs['data']
        self.assertEqual(data['context'], 'terminos medicos')
        self.assertNotIn('prompt', data)

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_hotwords_are_dropped_unless_the_api_has_a_field_for_them(self):
        # the OpenAI shape has none, so sending one would be a 400
        _, post = self.post(hotwords='gentelella,django')
        self.assertEqual(post.call_args.kwargs['data'], {})

        with override_settings(GENTELELLA_ASR_REMOTE_HOTWORDS_PARAM='keyterm'):
            _, post = self.post(hotwords='gentelella,django')
        self.assertEqual(post.call_args.kwargs['data']['keyterm'],
                         'gentelella,django')

    @override_settings(GENTELELLA_ASR_BACKEND='remote',
                       GENTELELLA_ASR_REMOTE_URL=URL)
    def test_an_unreachable_asr_is_a_bad_gateway(self):
        # Optional extra (asr-remote); the class is skipped without it.
        import requests  # noqa: PLC0415

        audio = SimpleUploadedFile('dictation.wav', b'RIFFfake',
                                   content_type='audio/wav')
        with mock.patch('requests.post',
                        side_effect=requests.ConnectionError('refused')):
            response = self.client.post(self.url, {'file': audio})

        self.assertEqual(response.status_code, 502)
        self.assertNotIn('refused', response.json()['error'])


class ResampleTestCase(TestCase):
    """_resample normalizes PyAV's several return shapes."""

    def test_a_single_frame_becomes_a_list(self):
        resampler = mock.Mock()
        resampler.resample.return_value = 'frame'
        self.assertEqual(asr._resample(resampler, object()), ['frame'])

    def test_a_list_is_passed_through(self):
        resampler = mock.Mock()
        resampler.resample.return_value = ['a', 'b']
        self.assertEqual(asr._resample(resampler, object()), ['a', 'b'])

    def test_nothing_to_emit_is_an_empty_list(self):
        resampler = mock.Mock()
        resampler.resample.return_value = None
        self.assertEqual(asr._resample(resampler, object()), [])

    def test_a_pyav_too_old_to_flush_yields_nothing(self):
        # old PyAV rejects resample(None) instead of flushing
        for error in (ValueError('no flush'), TypeError('frame required')):
            resampler = mock.Mock()
            resampler.resample.side_effect = error
            self.assertEqual(asr._resample(resampler, None), [])


@unittest.skipUnless(HAS_DECODER, 'the asr extra (av, numpy) is not installed')
class DecodeAudioTestCase(TestCase):
    """decode_to_f32_16k feeds the model, so its contract is what the model
    sees: mono, 16 kHz, float32 in [-1, 1]."""

    def test_it_resamples_to_16k_mono_float32(self):
        # Optional extra (asr); the class is skipped without it.
        import numpy as np  # noqa: PLC0415

        audio = asr.decode_to_f32_16k(io.BytesIO(wav_bytes(seconds=0.25,
                                                           rate=48000)))

        self.assertEqual(audio.dtype, np.float32)
        self.assertEqual(audio.ndim, 1)
        # 0.25 s at 16 kHz, give or take the resampler's own latency
        self.assertAlmostEqual(len(audio), 4000, delta=200)
        self.assertLessEqual(np.abs(audio).max(), 1.0)
        # a 440 Hz tone at amplitude 20000/32768 must survive as signal
        self.assertGreater(np.abs(audio).max(), 0.5)

    def test_it_reads_a_django_upload_without_a_temporary_file(self):
        upload = SimpleUploadedFile('dictation.wav', wav_bytes(seconds=0.1),
                                    content_type='audio/wav')
        audio = asr.decode_to_f32_16k(upload)
        self.assertGreater(len(audio), 0)


class TranscribeTestCase(TestCase):
    """transcribe() glues the decoder to the model."""

    def setUp(self):
        self.model = mock.Mock()
        self.model.recognize.return_value = '  hola mundo  '

    def transcribe(self, audio, **kwargs):
        with mock.patch.object(asr, '_get_model', return_value=self.model):
            with mock.patch.object(asr, 'decode_to_f32_16k',
                                   return_value=audio):
                return asr.transcribe(object(), **kwargs)

    def fake_audio(self, size=16000):
        return mock.Mock(size=size)

    def test_silence_never_loads_the_model(self):
        # a segment the VAD cut on noise decodes to nothing; downloading 670 MB
        # and running inference over it would be pure waste
        with mock.patch.object(asr, '_get_model') as get_model:
            with mock.patch.object(asr, 'decode_to_f32_16k',
                                   return_value=self.fake_audio(size=0)):
                self.assertEqual(asr.transcribe(object()), '')
        self.assertFalse(get_model.called)

    def test_the_result_is_stripped(self):
        self.assertEqual(self.transcribe(self.fake_audio()), 'hola mundo')

    def test_the_target_language_is_pinned_so_it_does_not_translate(self):
        # Parakeet-v3 translates to English unless target_language matches
        self.transcribe(self.fake_audio(), language='es')
        options = self.model.recognize.call_args.kwargs
        self.assertEqual(options['language'], 'es')
        self.assertEqual(options['target_language'], 'es')

    @override_settings(GENTELELLA_ASR_LANGUAGE='fr')
    def test_it_falls_back_to_the_configured_language(self):
        self.transcribe(self.fake_audio())
        options = self.model.recognize.call_args.kwargs
        self.assertEqual(options['language'], 'fr')
        self.assertEqual(options['target_language'], 'fr')

    @override_settings(GENTELELLA_ASR_PNC=False)
    def test_punctuation_and_capitals_can_be_turned_off(self):
        self.transcribe(self.fake_audio())
        self.assertIs(self.model.recognize.call_args.kwargs['pnc'], False)


class ExtractTextTestCase(TestCase):
    """The remote answer is normalized to a plain string."""

    def test_reads_both_shapes_and_never_returns_none(self):
        self.assertEqual(_extract_text({'text': 'flat'}), 'flat')
        self.assertEqual(
            _extract_text({'transcription': {'text': 'nested'}}), 'nested')
        self.assertEqual(_extract_text({'text': None}), '')
        self.assertEqual(_extract_text({}), '')
        self.assertEqual(_extract_text('not a dict'), '')
