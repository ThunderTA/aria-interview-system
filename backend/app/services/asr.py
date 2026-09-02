# TODO: Whisper-based ASR service.
# Buffer incoming audio chunks from the WS interview loop, run VAD to
# detect end-of-utterance, transcribe each completed utterance with
# Whisper (or faster-whisper for lower latency). See docs/architecture.md
# ("Real-Time Interview Loop") for how this plugs into app/routers/sessions.py.


async def transcribe_utterance(audio_bytes: bytes) -> str:
    raise NotImplementedError
