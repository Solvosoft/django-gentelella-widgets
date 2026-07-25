"""Optional in-process Parakeet-v3 ASR for the voice dictation widgets.

Requires the ``asr`` extra::

    pip install "djgentelella[asr]"   # onnx-asr[cpu,hub] + av + numpy

Everything heavy (onnx_asr, av, numpy) is imported lazily so importing
djgentelella stays free on installs without the extra. The model is loaded once
per process (first request pays a ~670 MB download from Hugging Face and the
warm-up cost); onnxruntime inference is thread-safe, so only the load is locked.

Configurable via settings:

- ``GENTELELLA_ASR_MODEL``        (default ``"nemo-parakeet-tdt-0.6b-v3"``)
- ``GENTELELLA_ASR_QUANTIZATION`` (default ``"int8"``)
- ``GENTELELLA_ASR_LANGUAGE``     (default ``"es"``)

Note: Parakeet does not support ``hotwords``/``initial_prompt`` biasing; those
widget attrs are ignored by this backend.
"""
import threading

from django.conf import settings

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import onnx_asr
                model_id = getattr(settings, 'GENTELELLA_ASR_MODEL',
                                   'nemo-parakeet-tdt-0.6b-v3')
                quant = getattr(settings, 'GENTELELLA_ASR_QUANTIZATION',
                                'int8')
                _model = onnx_asr.load_model(model_id, quantization=quant)
    return _model


def _resample(resampler, frame):
    """Resample one frame to a list of output frames. ``frame=None`` flushes the
    resampler (PyAV >= 9); older PyAV neither returns a list nor supports the
    flush call, both normalized here."""
    try:
        out = resampler.resample(frame)
    except (ValueError, TypeError):
        return []
    if out is None:
        return []
    return out if isinstance(out, list) else [out]


def decode_to_f32_16k(source):
    """Decode any container/codec PyAV supports (webm/opus, ogg, wav, ...) to a
    float32 mono 16 kHz waveform normalized to [-1, 1]. ``source`` may be a file
    path or a file-like object with ``read()``."""
    import av
    import numpy as np

    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    chunks = []
    with av.open(source) as container:
        stream = container.streams.audio[0]
        for frame in container.decode(stream):
            for rframe in _resample(resampler, frame):
                chunks.append(rframe.to_ndarray().reshape(-1))
        for rframe in _resample(resampler, None):   # flush
            chunks.append(rframe.to_ndarray().reshape(-1))
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def transcribe(source, language=None):
    """Decode ``source`` and return the transcribed text (empty string if the
    audio has no decodable samples).

    ``target_language`` is pinned to the source ``language`` so Parakeet-v3
    transcribes rather than translates to English. Punctuation & capitals
    (``pnc``) are on by default.
    """
    audio = decode_to_f32_16k(source)
    if audio.size == 0:
        return ''
    lang = language or getattr(settings, 'GENTELELLA_ASR_LANGUAGE', 'es')
    opts = {'pnc': getattr(settings, 'GENTELELLA_ASR_PNC', True)}
    if lang:
        opts['language'] = lang
        opts['target_language'] = lang  # transcribe, do not translate
    return _get_model().recognize(audio, **opts).strip()
