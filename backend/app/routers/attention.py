"""Live attention checks: one webcam frame in, what it shows out.

Frames are classified and dropped inside the request; only the state name and
the running counters are kept.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.session import AttentionSummary
from app.routers.sessions import _get_owned_session
from app.services import attention_service, cv_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["attention"])

MAX_FRAME_BYTES = 2 * 1024 * 1024


class AttentionCheckResult(BaseModel):
    state: str
    label: str
    attention: AttentionSummary


@router.post("/{session_id}/attention/check", response_model=AttentionCheckResult)
async def check_attention(
    session_id: str,
    frame: UploadFile,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Classify one frame: looking at the camera, down, away to one side, and so on."""
    if not settings.attention_checks_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Attention checks are turned off.")

    session = await _get_owned_session(db, session_id, str(current_user["_id"]), must_be_active=True)

    attention = session.get("attention") or attention_service.new_state()
    if attention_service.too_soon(attention):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Attention checked too recently.")

    data = await frame.read(MAX_FRAME_BYTES + 1)
    if len(data) > MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Camera frame is too large.")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No camera frame was received.")

    try:
        state = await cv_analysis.analyse_live_frame(data)
    except cv_analysis.VisualAnalysisError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except Exception as exc:
        logger.exception("Attention check failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Attention tracking is unavailable right now."
        ) from exc

    attention_service.apply_check(attention, state)
    # Conditional on the session still running, so a check in flight when the
    # session ends can't overwrite the finalised summary.
    await db.sessions.update_one(
        {"_id": session["_id"], "status": "in_progress"}, {"$set": {"attention": attention}}
    )

    return AttentionCheckResult(
        state=state,
        label=cv_analysis.STATE_LABELS[state],
        attention=attention_service.summary(attention),
    )
