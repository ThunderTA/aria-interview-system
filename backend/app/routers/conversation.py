"""Conversational interview: the candidate's spoken turn in, the interviewer's reply out.

Audio and frames are analysed then discarded, as on the classic answer path;
only the transcript and derived metrics are kept.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.session import ConversationTurn, SessionMode, SessionOut
from app.routers.sessions import (
    MAX_AUDIO_BYTES,
    MAX_FRAMES_PER_ANSWER,
    _get_owned_session,
    _require_identity_gate,
    _to_out,
)
from app.services import asr, conversation_service, cv_analysis, speech_metrics
from app.services.asr import TranscriptionError
from app.services.llm_client import LLMUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["conversation"])


class TurnResult(BaseModel):
    interviewer_turn: ConversationTurn
    closed: bool
    session: SessionOut


@router.post("/{session_id}/conversation/turn", response_model=TurnResult)
async def conversation_turn(
    session_id: str,
    audio: UploadFile,
    frames: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Take one spoken turn and return what the interviewer says next.

    Audio with no intelligible speech isn't an error here: in a conversation,
    the natural response is to ask the candidate to say it again.
    """
    session = await _get_owned_session(db, session_id, str(current_user["_id"]), must_be_active=True)
    if session.get("mode") != SessionMode.conversation.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session isn't a conversational interview.")
    _require_identity_gate(session)

    raw = await audio.read()
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Recording is too long (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
        )

    suffix = Path(audio.filename or "turn.webm").suffix or ".webm"
    try:
        transcript = await asr.transcribe(raw, suffix=suffix)
    except TranscriptionError:
        transcript = None

    delivery = visual = None
    if transcript is not None:
        delivery = speech_metrics.analyse(transcript)
        # Best-effort, as on the classic path: a camera problem must not cost the turn.
        if frames:
            try:
                visual = await cv_analysis.analyse_frames(
                    [await f.read() for f in frames[:MAX_FRAMES_PER_ANSWER]]
                )
            except Exception:
                logger.exception("Visual analysis failed; continuing the conversation without it")

    try:
        outcome = await conversation_service.take_turn(
            db, session, current_user, transcript, delivery, visual
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except conversation_service.ConversationClosed as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "This interview has already wrapped up.") from exc
    except conversation_service.ConversationConflict as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That reply arrived twice — the conversation has already moved on."
        ) from exc

    return TurnResult(
        interviewer_turn=outcome.interviewer_turn, closed=outcome.closed, session=_to_out(session)
    )
