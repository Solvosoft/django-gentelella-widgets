Voice dictation widgets
^^^^^^^^^^^^^^^^^^^^^^^^^

Two widgets add speech-to-text dictation to a form field:

- ``VoiceDictation`` (``djgentelella.widgets.core``) — a textarea with a
  microphone button.
- ``VoiceEditorTinymce`` (``djgentelella.widgets.tinymce``) — a TinyMCE
  rich-text editor with a microphone button in its own toolbar.

Both capture audio in the browser (Web Audio + voice-activity detection). The
dictation ``data-mode`` chooses how it is transcribed:

- ``segments`` (default) — each phrase (cut at a natural pause) is transcribed
  and appended live as you speak.
- ``single`` — nothing is sent until *Stop*, then the whole recording is
  transcribed in a single request.
- ``hybrid`` — segments appear live, then on *Stop* the whole recording is
  re-transcribed and replaces them, trading the live per-segment result for the
  broader ASR context of a single whole-file pass.

**Usage**

.. code:: python

    from django import forms
    from django.urls import reverse_lazy
    from djgentelella.forms.forms import GTForm
    from djgentelella.widgets import core as genwidgets
    from djgentelella.widgets import tinymce as tinymce_widget

    class DictationForm(GTForm, forms.Form):
        notes = forms.CharField(
            required=False,
            widget=genwidgets.VoiceDictation(
                url=reverse_lazy('voice_transcribe'), language='es'),
        )
        body = forms.CharField(
            required=False,
            widget=tinymce_widget.VoiceEditorTinymce(
                url=reverse_lazy('voice_transcribe'), language='es'),
        )

``url`` is the transcription endpoint and ``language`` the spoken language.

.. note:: ``getUserMedia`` requires a secure context — the page must be served
   over HTTPS or from ``localhost``.

**Transcription endpoint**

``djgentelella`` ships a ready-to-use endpoint, ``djgentelella:voice_transcribe``
(``VoiceTranscribeView``), that accepts a POST with an audio ``file`` (plus
optional ``language``/``hotwords``/``initial_prompt``) and returns
``{"text": "..."}``. It has two interchangeable backends selected by settings:

``local``
    Runs NVIDIA Parakeet-v3 in-process (CPU) via the optional extra
    ``pip install "djgentelella[voice]"``. The model (~670 MB) downloads from
    Hugging Face on first use.

``remote``
    Forwards the audio to an external ASR HTTP API
    (``GENTELELLA_ASR_REMOTE_URL``), presenting
    ``Authorization: Bearer <GENTELELLA_ASR_REMOTE_TOKEN>`` when configured. Use
    this when the host can't run the model in-process.

    The request defaults to the OpenAI ``POST /v1/audio/transcriptions`` shape
    (``file`` + ``model``/``language``/``prompt``, response ``{"text": ...}``),
    so a stock config talks to **OpenAI, Groq, vLLM or faster-whisper-server**
    unchanged. The three ``GENTELELLA_ASR_REMOTE_*_PARAM``/``_MODEL`` settings
    below remap the field names for other servers — e.g. Deepgram
    (``HOTWORDS_PARAM=keyterm``). ``model`` is only sent when
    ``GENTELELLA_ASR_REMOTE_MODEL`` is set; otherwise the server uses its own
    default model.

If ``GENTELELLA_ASR_BACKEND`` is unset it defaults to ``remote`` when a remote
URL is configured, otherwise ``local``.

**Settings**

.. list-table::
   :header-rows: 1
   :widths: 32 43 25

   * - Setting
     - Purpose
     - Default
   * - ``GENTELELLA_ASR_BACKEND``
     - ``local`` or ``remote``
     - auto (remote if a URL is set)
   * - ``GENTELELLA_ASR_REMOTE_URL``
     - External ASR endpoint (remote backend)
     - *(none)*
   * - ``GENTELELLA_ASR_REMOTE_TOKEN``
     - Bearer token for the external ASR
     - ``''`` (no header)
   * - ``GENTELELLA_ASR_TIMEOUT``
     - Remote request timeout (seconds)
     - ``120``
   * - ``GENTELELLA_ASR_REMOTE_MODEL``
     - Model id sent to the remote ASR (omitted when unset → server default)
     - *(none)*
   * - ``GENTELELLA_ASR_REMOTE_PROMPT_PARAM``
     - Remote field name for the biasing prompt (from ``initial_prompt``)
     - ``prompt``
   * - ``GENTELELLA_ASR_REMOTE_HOTWORDS_PARAM``
     - Remote field name for keyword biasing (from ``hotwords``); dropped if unset
     - *(none)*
   * - ``GENTELELLA_ASR_MODEL``
     - Local model id
     - ``nemo-parakeet-tdt-0.6b-v3``
   * - ``GENTELELLA_ASR_QUANTIZATION``
     - Local model quantization
     - ``int8``
   * - ``GENTELELLA_ASR_LANGUAGE``
     - Default language (local backend)
     - ``es``
   * - ``GENTELELLA_ASR_PNC``
     - Punctuation & capitalization (local)
     - ``True``

**Per-widget data-\* options**

Beyond ``url`` and ``language`` (kwargs), the widgets accept tuning through
``attrs``:

- ``data-hotwords`` / ``data-initial-prompt`` — biasing context forwarded to
  the endpoint (used by Whisper-style backends; **Parakeet-v3 ignores them**).
- ``data-vad-silence-ms`` (default 600), ``data-vad-min-speech-ms`` (500),
  ``data-vad-max-segment-ms`` (10000), ``data-rms-threshold`` (0.008),
  ``data-pool-size`` (3) — voice-activity-detection / concurrency tuning. The
  defaults cut at short ~0.6 s pauses so segments appear live as you speak; raise
  ``data-vad-silence-ms``/``data-vad-min-speech-ms`` for longer segments (more
  ASR context per segment).
- ``data-insert-mode="paragraph"`` — (TinyMCE) wrap each dictated fragment in
  its own ``<p>`` instead of inline.
- ``data-mode`` — dictation mode: ``segments`` (default), ``single`` or
  ``hybrid`` (see the top of this section).

.. code:: python

    genwidgets.VoiceDictation(
        url=reverse_lazy('voice_transcribe'), language='es',
        attrs={'data-hotwords': 'Django, gentelella', 'data-vad-silence-ms': 1000},
    )

.. note:: Parakeet-v3 cannot be biased toward specific vocabulary, so proper
   nouns and acronyms may be mis-transcribed. A Whisper backend (which accepts
   ``hotwords``/``initial_prompt``) handles those better.
