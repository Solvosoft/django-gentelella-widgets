import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.views import View

logger = logging.getLogger(__name__)

BACKENDS = ('local', 'remote')
# OpenAI's /v1/audio/transcriptions caps uploads at 25 MB and the widget sends
# WAV, so this is a generous ceiling for a single dictated phrase.
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _extract_text(payload):
    """Normalize the JSON of an external ASR to a plain text string.

    Accepts both ``{"text": ...}`` and a nested
    ``{"transcription": {"text": ...}}`` shape.
    """
    if not isinstance(payload, dict):
        return ''
    if isinstance(payload.get('transcription'), dict):
        return payload['transcription'].get('text', '') or ''
    return payload.get('text', '') or ''


class VoiceTranscribeView(View):
    """Transcription endpoint for the voice dictation widgets, with two
    interchangeable backends selected by settings:

    - ``local``  — in-process Parakeet-v3 (needs ``pip install
      "djgentelella[asr]"``). Use when the load is light.
    - ``remote`` — forward the audio to an external ASR HTTP API (needs
      ``pip install "djgentelella[asr-remote]"`` and
      ``GENTELELLA_ASR_REMOTE_URL``). Use when you need more
      power than the host can provide in-process. When
      ``GENTELELLA_ASR_REMOTE_TOKEN`` is set, gentelella presents it as an
      ``Authorization: Bearer <token>`` header (the external API should always
      require one).

    Backend selection (``GENTELELLA_ASR_BACKEND``): if unset, defaults to
    ``remote`` when ``GENTELELLA_ASR_REMOTE_URL`` is configured, otherwise
    ``local``.

    Accepts a POST with the audio in the ``file`` field (plus optional
    ``language``, ``hotwords`` and ``initial_prompt``; ``language`` drives the
    local backend and is forwarded to the remote one, the others are forwarded
    to remote backends that support them) and returns ``{"text": ...}``.

    Uploads larger than ``GENTELELLA_ASR_MAX_UPLOAD_BYTES`` (25 MB by default)
    are rejected with a 413: transcription is expensive in both backends (CPU
    in-process, billable API calls remotely) and each request holds a worker
    for up to ``GENTELELLA_ASR_TIMEOUT`` seconds.

    The view requires an authenticated user and enforces it itself, so it must
    not be wrapped in ``login_required``: that redirects, and the widget's
    ``fetch`` would follow the 302 and choke on the login page in ``.json()``.
    """

    def dispatch(self, request, *args, **kwargs):
        # Transcription costs cpu or money, so it is never open to the world.
        # 403 with a json body rather than a redirect: the caller is a fetch(),
        # and it has to be able to tell "log in again" from a server error.
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'authentication required'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_backend(self):
        """Resolve the configured backend, failing loudly on a typo.

        Both settings are commonly wired to ``os.getenv``, which yields ``''``
        rather than leaving the setting out, so an empty value counts as unset.
        """
        remote_url = getattr(settings, 'GENTELELLA_ASR_REMOTE_URL', None) or None
        backend = getattr(settings, 'GENTELELLA_ASR_BACKEND', None) or None
        if backend is None:
            backend = 'remote' if remote_url else 'local'
        elif backend not in BACKENDS:
            raise ImproperlyConfigured(
                'GENTELELLA_ASR_BACKEND must be one of %s, got %r' % (
                    ', '.join(BACKENDS), backend))
        return backend, remote_url

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('file')
        if upload is None:
            return JsonResponse({'error': 'no audio file'}, status=400)

        max_bytes = getattr(settings, 'GENTELELLA_ASR_MAX_UPLOAD_BYTES',
                            DEFAULT_MAX_UPLOAD_BYTES)
        if max_bytes and upload.size > max_bytes:
            logger.warning('Rejected a %s byte audio upload (limit %s)',
                           upload.size, max_bytes)
            return JsonResponse(
                {'error': 'audio file too large'}, status=413)

        language = request.POST.get('language') or None
        backend, remote_url = self.get_backend()

        if backend == 'remote':
            return self._transcribe_remote(request, upload, remote_url)
        return self._transcribe_local(upload, language)

    def _transcribe_local(self, upload, language):
        # asr module import is light (onnx_asr/av are imported lazily inside its
        # functions), so a missing extra surfaces as ImportError at call time.
        # Keep that import out of the try below: an ImportError raised *inside*
        # transcribe() (a broken onnxruntime ABI, say) is not a missing extra
        # and must not be reported as one.
        from djgentelella.voice.asr import transcribe
        try:
            # UploadedFile is a file-like object; av.open reads it directly,
            # avoiding a full in-memory copy of the (possibly multi-MB) audio.
            text = transcribe(upload, language=language)
        except ModuleNotFoundError as exc:
            logger.warning('Local ASR backend is unavailable: %s', exc)
            return JsonResponse(
                {'error': 'asr extra not installed: '
                          'pip install "djgentelella[asr]"'},
                status=501)
        except Exception:
            logger.exception('Local ASR transcription failed')
            return JsonResponse(
                {'error': 'transcription failed'}, status=500)
        return JsonResponse({'text': text})

    def _remote_data(self, request):
        """Build the non-file POST fields for the external ASR, mapping the
        engine's internal field names onto whatever the target API expects.

        Defaults are OpenAI-compatible (``POST /v1/audio/transcriptions``), so a
        stock config talks to OpenAI, Groq, vLLM, faster-whisper-server, etc.
        The three settings below remap the fields for other servers (e.g.
        Deepgram: hotwords param ``keyterm``):

        - ``GENTELELLA_ASR_REMOTE_MODEL``        model id; omitted when unset so
          the server falls back to its own default model.
        - ``GENTELELLA_ASR_REMOTE_PROMPT_PARAM`` field for the biasing prompt
          (from the widget's ``initial_prompt``). Default ``"prompt"``.
        - ``GENTELELLA_ASR_REMOTE_HOTWORDS_PARAM`` field for keyword biasing
          (from the widget's ``hotwords``). Default ``None`` — dropped, since
          the OpenAI shape has no such field.
        """
        data = {}

        # Only send `model` when configured; otherwise let the server pick its
        # default (some OpenAI-compatible servers ignore it / serve one model).
        model = getattr(settings, 'GENTELELLA_ASR_REMOTE_MODEL', None)
        if model:
            data['model'] = model

        language = request.POST.get('language')
        if language:
            data['language'] = language

        prompt = request.POST.get('initial_prompt')
        if prompt:
            prompt_param = getattr(
                settings, 'GENTELELLA_ASR_REMOTE_PROMPT_PARAM', 'prompt')
            data[prompt_param] = prompt

        hotwords = request.POST.get('hotwords')
        hotwords_param = getattr(
            settings, 'GENTELELLA_ASR_REMOTE_HOTWORDS_PARAM', None)
        if hotwords and hotwords_param:
            data[hotwords_param] = hotwords

        return data

    def _transcribe_remote(self, request, upload, remote_url):
        if not remote_url:
            logger.error('GENTELELLA_ASR_BACKEND is "remote" but '
                         'GENTELELLA_ASR_REMOTE_URL is not configured')
            return JsonResponse(
                {'error': 'GENTELELLA_ASR_REMOTE_URL is not configured'},
                status=500)
        try:
            import requests
        except ImportError as exc:
            logger.warning('Remote ASR backend is unavailable: %s', exc)
            return JsonResponse(
                {'error': 'asr-remote extra not installed: '
                          'pip install "djgentelella[asr-remote]"'},
                status=501)

        # Pass the file object so requests streams it instead of buffering the
        # whole audio in memory. The engine sends WAV, hence the default.
        files = {
            'file': (upload.name, upload,
                     upload.content_type or 'audio/wav'),
        }
        data = self._remote_data(request)
        # gentelella manages the token the external ASR API requires; always
        # present it as a Bearer header when configured.
        headers = {}
        token = getattr(settings, 'GENTELELLA_ASR_REMOTE_TOKEN', None)
        if token:
            headers['Authorization'] = 'Bearer ' + token
        timeout = getattr(settings, 'GENTELELLA_ASR_TIMEOUT', 120)
        try:
            resp = requests.post(
                remote_url, files=files, data=data, headers=headers,
                timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException:
            # The client gets a generic message on purpose, but the operator
            # needs to tell an expired token from a timeout from bad JSON.
            logger.exception('Remote ASR request to %s failed', remote_url)
            return JsonResponse(
                {'error': 'ASR server unavailable'}, status=502)
        return JsonResponse({'text': _extract_text(payload)})
