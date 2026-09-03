"""Speech-to-text via faster-whisper, running locally.

No audio leaves the machine and no API key is needed, which keeps the
project's "open-source, Rs. 0" claim intact. faster-whisper bundles its own
media decoding through PyAV, so there is no system ffmpeg dependency either.

The model is loaded once and reused: loading costs ~15s, transcription runs
several times faster than realtime, so a per-request load would dominate.
"""

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = asyncio.Lock()


class TranscriptionError(RuntimeError):
    """Audio could not be decoded or contained no speech."""


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class Transcript:
    text: str
    duration: float
    words: list[Word] = field(default_factory=list)


async def _get_model():
    """Load the Whisper model once, guarding against concurrent first requests."""
    global _model
    if _model is not None:
        return _model

    async with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel

            logger.info("Loading Whisper model %r…", settings.whisper_model)
            _model = await asyncio.to_thread(
                WhisperModel,
                settings.whisper_model,
                device="cpu",
                compute_type=settings.whisper_compute_type,
            )
            logger.info("Whisper model ready")
    return _model


async def warm_up() -> None:
    """Pre-load the model so the first candidate doesn't pay the load cost."""
    try:
        await _get_model()
    except Exception:
        logger.exception("Whisper warm-up failed; it will load on first use instead")


async def transcribe(audio_bytes: bytes, suffix: str = ".webm") -> Transcript:
    """Transcribe recorded audio into text plus word-level timings.

    The timings are what make the delivery metrics (pace, pauses) possible, so
    they are always requested.
    """
    if not audio_bytes:
        raise TranscriptionError("No audio was recorded.")

    model = await _get_model()

    # faster-whisper reads from a path; browsers hand us an opaque container.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = Path(tmp.name)

    try:
        return await asyncio.to_thread(_run_transcription, model, str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)


def _run_transcription(model, path: str) -> Transcript:
    try:
        segments, info = model.transcribe(path, word_timestamps=True, vad_filter=True)
        segments = list(segments)
    except Exception as exc:
        raise TranscriptionError("That recording could not be read.") from exc

    text = " ".join(segment.text.strip() for segment in segments).strip()
    if not text:
        raise TranscriptionError("No speech was detected in the recording.")

    words = [
        Word(text=w.word.strip(), start=w.start, end=w.end)
        for segment in segments
        for w in (segment.words or [])
    ]
    return Transcript(text=text, duration=info.duration, words=words)
