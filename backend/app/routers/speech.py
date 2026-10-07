"""The interviewer's voice: text in, WAV audio out, synthesised on this machine."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.deps import get_current_user
from app.services import tts

# Authenticated so the endpoint can't be used as a free text-to-speech service.
router = APIRouter(prefix="/speech", tags=["speech"], dependencies=[Depends(get_current_user)])


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts.MAX_TEXT_CHARS)


@router.post("", response_class=Response, responses={200: {"content": {"audio/wav": {}}}})
async def speak(payload: SpeechRequest):
    """Synthesise one utterance. 503 tells the client to fall back to the browser's voice."""
    if not settings.tts_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The interviewer's voice is turned off.")
    try:
        audio = await tts.synthesize(payload.text)
    except tts.SpeechUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
