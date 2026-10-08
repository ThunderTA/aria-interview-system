"""Identity verification endpoints for an interview session.

Frames are read into memory, analysed, and dropped at the end of the request.
Responses carry outcomes and counters only - never embeddings or similarity
scores.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.identity import IdentityCheckResult, IdentityGate, IdentityVerifyResult
from app.routers.sessions import _get_owned_session
from app.services import face_identity, identity_service

router = APIRouter(prefix="/sessions", tags=["identity"])

MAX_START_FRAMES = 5
# A 640px JPEG is ~60 KB; this leaves room for larger cameras without
# accepting arbitrary uploads.
MAX_FRAME_BYTES = 2 * 1024 * 1024


async def _read_frame(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_FRAME_BYTES + 1)
    if len(data) > MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Camera frame is too large.")
    return data


async def _session_requiring_identity(db: AsyncIOMotorDatabase, session_id: str, user: dict) -> dict:
    session = await _get_owned_session(db, session_id, str(user["_id"]), must_be_active=True)
    if not (session.get("identity") or {}).get("required"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Identity verification isn't enabled for this session.")
    return session


def _engine_unavailable() -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Face verification isn't available right now. Try again in a minute.",
    )


@router.post("/{session_id}/identity/verify", response_model=IdentityVerifyResult)
async def verify_identity(
    session_id: str,
    frames: list[UploadFile] = File(...),
    continue_unmatched: bool = Form(False),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Start-of-interview check on a short burst of webcam frames.

    Matches against the resume photo, or enrolls the face when there isn't one.
    With `continue_unmatched`, a candidate whose resume photo has repeatedly
    failed to match may proceed - recorded as an integrity event.
    """
    session = await _session_requiring_identity(db, session_id, current_user)
    state = session["identity"]
    if state["gate"] != IdentityGate.pending.value:
        return IdentityVerifyResult(
            passed=True, message="Identity already confirmed.", identity=identity_service.summary(state)
        )

    frame_bytes = [data for data in [await _read_frame(f) for f in frames[:MAX_START_FRAMES]] if data]
    if not frame_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No camera frames were received.")

    try:
        result = await identity_service.verify_start(
            db, session, frame_bytes, continue_unmatched=continue_unmatched
        )
    except face_identity.FaceEngineUnavailable as exc:
        raise _engine_unavailable() from exc
    except identity_service.ContinueNotAllowed as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Try matching your resume photo a few more times first."
        ) from exc

    return IdentityVerifyResult(
        passed=result.passed,
        outcome=result.outcome,
        hint=result.hint,
        message=result.message,
        identity=identity_service.summary(state),
    )


@router.post("/{session_id}/identity/skip", response_model=IdentityVerifyResult)
async def skip_identity(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Continue without verification - only permitted while face verification can't run."""
    session = await _session_requiring_identity(db, session_id, current_user)
    state = session["identity"]
    if state["gate"] != IdentityGate.pending.value:
        return IdentityVerifyResult(
            passed=True, message="Identity already confirmed.", identity=identity_service.summary(state)
        )

    try:
        await identity_service.skip_unavailable(db, session)
    except identity_service.EngineStillAvailable as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Face verification is working again - verify with your camera to continue."
        ) from exc

    return IdentityVerifyResult(
        passed=True,
        message="Continuing without identity verification. This will be noted in your report.",
        identity=identity_service.summary(state),
    )


@router.post("/{session_id}/identity/check", response_model=IdentityCheckResult)
async def check_identity(
    session_id: str,
    frame: UploadFile | None = File(None),
    camera_off: bool = Form(False),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """One periodic check during the interview.

    Send `camera_off=true` without a frame when the camera isn't running: that
    still counts as a check in which no face could be seen.
    """
    session = await _session_requiring_identity(db, session_id, current_user)
    state = session["identity"]
    if state["gate"] not in (IdentityGate.verified.value, IdentityGate.unmatched.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Identity checks haven't started for this session.")

    data = await _read_frame(frame) if frame is not None and not camera_off else None
    try:
        outcome, hint = await identity_service.run_check(db, session, data or None)
    except identity_service.CheckTooSoon as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Identity checked too recently.") from exc
    except identity_service.ReferenceUnavailable as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This session's identity reference has expired."
        ) from exc
    except face_identity.FaceEngineUnavailable as exc:
        raise _engine_unavailable() from exc

    return IdentityCheckResult(outcome=outcome, hint=hint, identity=identity_service.summary(state))
