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
- ``GENTELELLA_ASR_PNC``          (default ``True``) -- punctuation & capitals

Note: Parakeet does not support ``hotwords``/``initial_prompt`` biasing; those
widget attrs are ignored by this backend.
"""
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import onnx_asr  # noqa: PLC0415
                model_id = getattr(settings, 'GENTELELLA_ASR_MODEL',
                                   'nemo-parakeet-tdt-0.6b-v3')
                quant = getattr(settings, 'GENTELELLA_ASR_QUANTIZATION',
                                'int8')
                # Worth a line: the first call downloads ~670 MB and blocks the
                # request thread doing it, which otherwise looks like a hang.
                logger.info('Loading ASR model %s (%s); the first load '
                            'downloads it from Hugging Face', model_id, quant)
                _model = onnx_asr.load_model(model_id, quantization=quant)
                logger.info('ASR model %s ready', model_id)
    return _model


def _resample(resampler, frame):
    """Resample one frame to a list of output frames.

    ``frame=None`` flushes the resampler, which only PyAV >= 9 supports; older
    versions raise instead, and since there is nothing buffered to lose that is
    the one failure worth ignoring. A failure on a real frame is re-raised on
    purpose: swallowing it turned a decode error into "empty audio", so
    :func:`transcribe` returned an empty string and nothing anywhere said why.
    """
    try:
        out = resampler.resample(frame)
    except (ValueError, TypeError):
        if frame is not None:
            raise
        logger.debug('this PyAV cannot flush the resampler; skipping the flush')
        return []
    if out is None:
        return []
    return out if isinstance(out, list) else [out]


def decode_to_f32_16k(source):
    """Decode any container/codec PyAV supports (webm/opus, ogg, wav, ...) to a
    float32 mono 16 kHz waveform normalized to [-1, 1]. ``source`` may be a file
    path or a file-like object with ``read()``."""
    import av  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

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

    ``language`` defaults to ``GENTELELLA_ASR_LANGUAGE``. Whatever it resolves
    to is also passed to the model as ``target_language``, which is what stops
    Parakeet-v3 from translating to English instead of transcribing.
    Punctuation & capitals (``GENTELELLA_ASR_PNC``) are on by default.
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
