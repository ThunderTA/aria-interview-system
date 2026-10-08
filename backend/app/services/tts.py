"""Text-to-speech for the conversational interviewer, running locally.

Kokoro (82M parameters, Apache-2.0) runs through onnxruntime, which
faster-whisper already installed, so the interviewer's voice keeps ARIA's
"no API key, no per-interview cost, works offline" property. On an Apple M4 it
synthesises about five times faster than real time and a first sentence in
under half a second - fast enough for the client to start speaking a reply
sentence by sentence rather than waiting for all of it.

Audio is generated per request and returned; nothing is written to disk.
"""

import asyncio
import io
import logging
import re
import threading
import time
import wave
from pathlib import Path

import numpy as np

from app.core.config import settings
from app.services.model_download import ModelDownloadError, ensure_model_file

logger = logging.getLogger(__name__)

MODEL_DIR = Path.home() / ".cache" / "aria" / "models" / "kokoro"
_RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
# The full-precision graph rather than the int8 one: on Apple Silicon it
# synthesised twice as fast (real-time factor 0.21 vs 0.45) for 3.5x the size.
_FILES = {
    "model": ("kokoro-v1.0.onnx", "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    "voices": ("voices-v1.0.bin", "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
}
MAX_TEXT_CHARS = 800
DOWNLOAD_TIMEOUT_SECONDS = 120
RETRY_AFTER_FAILURE_SECONDS = 60

# A curated handful rather than all 28 English voices Kokoro ships: enough that
# nobody is stuck with a voice they dislike, few enough to pick from in one
# glance. Labels describe what a candidate actually notices.
VOICES = (
    {"id": "af_heart", "label": "Maya", "accent": "American", "tone": "warm"},
    {"id": "af_bella", "label": "Bella", "accent": "American", "tone": "bright"},
    {"id": "am_michael", "label": "Michael", "accent": "American", "tone": "measured"},
    {"id": "am_fenrir", "label": "Felix", "accent": "American", "tone": "deep"},
    {"id": "bf_emma", "label": "Emma", "accent": "British", "tone": "crisp"},
    {"id": "bm_george", "label": "George", "accent": "British", "tone": "low"},
)
VOICE_IDS = frozenset(voice["id"] for voice in VOICES)

_MARKUP = re.compile(r"[*_`#>|~\[\]{}]+")


class SpeechUnavailable(RuntimeError):
    """The voice model couldn't be downloaded, loaded, or run."""


_engine = None
_last_failure_at = 0.0
_load_lock = threading.Lock()
# The phonemizer underneath Kokoro isn't documented as thread-safe.
_synth_lock = threading.Lock()


def resolve_voice(voice: str | None) -> str:
    """The requested voice if it's one we offer, else the configured default."""
    return voice if voice in VOICE_IDS else settings.tts_voice


def _load():
    global _engine, _last_failure_at
    if _engine is not None:
        return _engine

    with _load_lock:
        if _engine is None:
            if time.monotonic() - _last_failure_at < RETRY_AFTER_FAILURE_SECONDS:
                raise SpeechUnavailable("The interviewer's voice is temporarily unavailable.")
            try:
                from kokoro_onnx import Kokoro

                paths = {
                    key: ensure_model_file(
                        MODEL_DIR / name, f"{_RELEASE}/{name}", digest, timeout=DOWNLOAD_TIMEOUT_SECONDS
                    )
                    for key, (name, digest) in _FILES.items()
                }
                engine = Kokoro(str(paths["model"]), str(paths["voices"]))
                available = set(engine.get_voices())
                missing = VOICE_IDS - available
                if settings.tts_voice not in available:
                    raise SpeechUnavailable(f"Unknown interviewer voice {settings.tts_voice!r}.")
                if missing:
                    logger.warning("Voice model is missing offered voices: %s", sorted(missing))
            except SpeechUnavailable:
                _last_failure_at = time.monotonic()
                raise
            except (ModelDownloadError, ImportError, Exception) as exc:
                _last_failure_at = time.monotonic()
                raise SpeechUnavailable("The interviewer's voice couldn't be loaded.") from exc
            _engine = engine
            logger.info("Interviewer voice ready (default %s)", settings.tts_voice)
    return _engine


async def warm_up() -> None:
    """Fetch and load the voice at startup so the first greeting isn't delayed."""
    try:
        await asyncio.to_thread(_load)
    except SpeechUnavailable:
        logger.warning("Interviewer voice unavailable at startup; the browser voice will be used")


def clean_text(text: str) -> str:
    """Strip markup a language model might emit, which would otherwise be read aloud."""
    return " ".join(_MARKUP.sub(" ", text).split())


def _synthesize_sync(text: str, voice: str) -> bytes:
    engine = _load()
    with _synth_lock:
        samples, rate = engine.create(text, voice=voice, speed=settings.tts_speed, lang="en-us")

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


async def synthesize(text: str, voice: str | None = None) -> bytes:
    """WAV audio of `text`. Raises SpeechUnavailable, or ValueError for empty text."""
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("There's nothing to say.")
    try:
        return await asyncio.to_thread(_synthesize_sync, cleaned, resolve_voice(voice))
    except SpeechUnavailable:
        raise
    except Exception as exc:
        logger.exception("Speech synthesis failed")
        raise SpeechUnavailable("The interviewer's voice couldn't read that.") from exc
