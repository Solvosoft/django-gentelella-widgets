from django.conf import settings
from django.http import JsonResponse
from django.views import View


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
      "djgentelella[voice]"``). Use when the load is light.
    - ``remote`` — forward the audio to an external ASR HTTP API (needs
      ``requests`` and ``GENTELELLA_ASR_REMOTE_URL``). Use when you need more
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
    """

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('file')
        if upload is None:
            return JsonResponse({'error': 'no audio file'}, status=400)

        language = request.POST.get('language') or None
        remote_url = getattr(settings, 'GENTELELLA_ASR_REMOTE_URL', None)
        backend = getattr(settings, 'GENTELELLA_ASR_BACKEND',
                          'remote' if remote_url else 'local')

        if backend == 'remote':
            return self._transcribe_remote(request, upload, remote_url)
        return self._transcribe_local(upload, language)

    def _transcribe_local(self, upload, language):
        # asr module import is light (onnx_asr/av are imported lazily inside its
        # functions), so a missing extra surfaces as ImportError at call time.
        from djgentelella.voice.asr import transcribe
        try:
            # UploadedFile is a file-like object; av.open reads it directly,
            # avoiding a full in-memory copy of the (possibly multi-MB) audio.
            text = transcribe(upload, language=language)
        except ImportError:
            return JsonResponse(
                {'error': 'voice extra not installed: '
                          'pip install "djgentelella[voice]"'},
                status=501)
        except Exception:
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
            return JsonResponse(
                {'error': 'GENTELELLA_ASR_REMOTE_URL is not configured'},
                status=500)
        try:
            import requests
        except ImportError:
            return JsonResponse(
                {'error': 'remote ASR backend needs the requests package'},
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
            return JsonResponse(
                {'error': 'ASR server unavailable'}, status=502)
        return JsonResponse({'text': _extract_text(payload)})
