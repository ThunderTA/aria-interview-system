import logging
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.session import AnswerSubmit, SessionCreate, SessionOut, SessionStatus
from app.services import asr, cv_analysis, identity_service, interview_service, speech_metrics
from app.services.asr import TranscriptionError
from app.services.llm_client import LLMUnavailableError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

# A few minutes of compressed speech; well beyond a 90-second answer.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
# At ~1 fps this covers a very long answer; anything beyond is redundant for
# gaze and posture, which don't change meaningfully frame to frame.
MAX_FRAMES_PER_ANSWER = 180


def _oid(session_id: str) -> ObjectId:
    try:
        return ObjectId(session_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.") from exc


def _to_out(doc: dict) -> SessionOut:
    return SessionOut(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        role=doc["role"],
        status=doc["status"],
        started_at=doc["started_at"],
        ended_at=doc.get("ended_at"),
        overall_score=doc.get("overall_score"),
        content_score_avg=doc.get("content_score_avg"),
        delivery_score_avg=doc.get("delivery_score_avg"),
        visual_score_avg=doc.get("visual_score_avg"),
        questions=doc.get("questions", []),
        identity=identity_service.summary(doc["identity"]) if doc.get("identity") else None,
    )


def _require_identity_gate(session: dict) -> None:
    if not identity_service.gate_open(session):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Confirm your identity with your camera before answering.",
        )


async def _get_owned_session(
    db: AsyncIOMotorDatabase, session_id: str, user_id: str, *, must_be_active: bool = False
) -> dict:
    doc = await db.sessions.find_one({"_id": _oid(session_id), "user_id": user_id})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    if must_be_active and doc["status"] != SessionStatus.in_progress:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session has already ended.")
    return doc


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Start a session and generate its first question."""
    user_id = str(current_user["_id"])
    doc = {
        "user_id": user_id,
        "role": payload.role.value,
        "status": SessionStatus.in_progress.value,
        "started_at": datetime.now(timezone.utc),
        "ended_at": None,
        "overall_score": None,
        "content_score_avg": None,
        "delivery_score_avg": None,
        "visual_score_avg": None,
        "questions": [],
        "identity": await identity_service.initial_state(db, user_id),
    }

    try:
        first_question = await interview_service.build_next_question(
            db, doc, user_id, starting_difficulty=payload.starting_difficulty
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    doc["questions"] = [first_question]
    result = await db.sessions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_out(doc)


@router.get("", response_model=list[SessionOut])
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.sessions.find({"user_id": str(current_user["_id"])}).sort("started_at", -1).limit(50)
    return [_to_out(doc) async for doc in cursor]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return _to_out(await _get_owned_session(db, session_id, str(current_user["_id"])))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    result = await db.sessions.delete_one(
        {"_id": _oid(session_id), "user_id": str(current_user["_id"])}
    )
    if result.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    await identity_service.delete_session_reference(db, _oid(session_id))


@router.post("/{session_id}/answer", response_model=SessionOut)
async def submit_answer(
    session_id: str,
    payload: AnswerSubmit,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Score the answer to the current question.

    Deliberately does *not* generate the next question: on a local model that
    would roughly double the wait before the candidate sees any feedback. The
    client calls POST /next once it has the score, so reading the feedback
    overlaps with generating what comes next.

    Until the WebSocket + Whisper path lands, the client sends an already
    transcribed answer here; the scoring and adaptation logic is identical
    either way.
    """
    user_id = str(current_user["_id"])
    session = await _get_owned_session(db, session_id, user_id, must_be_active=True)
    _require_identity_gate(session)

    current = session["questions"][-1]
    if current.get("content_score") is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question has already been answered.")

    try:
        await interview_service.score_and_advance(db, session, payload.transcript)
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    await db.sessions.update_one(
        {"_id": session["_id"]}, {"$set": {"questions": session["questions"]}}
    )
    return _to_out(session)


@router.post("/{session_id}/answer/audio", response_model=SessionOut)
async def submit_spoken_answer(
    session_id: str,
    audio: UploadFile,
    frames: list[UploadFile] = File(default=[]),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Transcribe a recorded answer, measure delivery and visuals, then score it.

    Same path as the typed endpoint once there's a transcript — the difference
    is that a spoken answer also yields pace, pause and filler metrics, and
    (when the camera was on) gaze, expression and posture.

    Audio and frames are analysed then discarded; only the transcript and the
    derived numbers are stored, per the proposal's "no raw media retained"
    commitment.
    """
    user_id = str(current_user["_id"])
    session = await _get_owned_session(db, session_id, user_id, must_be_active=True)
    _require_identity_gate(session)

    current = session["questions"][-1]
    if current.get("content_score") is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question has already been answered.")

    raw = await audio.read()
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Recording is too long (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
        )

    suffix = Path(audio.filename or "answer.webm").suffix or ".webm"
    try:
        transcript = await asr.transcribe(raw, suffix=suffix)
    except TranscriptionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    metrics = speech_metrics.analyse(transcript)
    metrics["note"] = speech_metrics.describe(metrics)

    # Visual analysis is best-effort: no camera, a denied permission or a
    # failure here must not cost the candidate their answer.
    visual = None
    if frames:
        try:
            frame_bytes = [await f.read() for f in frames[:MAX_FRAMES_PER_ANSWER]]
            visual = await cv_analysis.analyse_frames(frame_bytes)
        except Exception:
            logger.exception("Visual analysis failed; scoring the answer without it")

    try:
        await interview_service.score_and_advance(
            db, session, transcript.text, delivery=metrics, visual=visual
        )
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    await db.sessions.update_one(
        {"_id": session["_id"]}, {"$set": {"questions": session["questions"]}}
    )
    return _to_out(session)


@router.post("/{session_id}/next", response_model=SessionOut)
async def next_question(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Generate the next question at the difficulty the RL policy recommends.

    A no-op if the current question is still unanswered or the session has run
    its full length, so the client can call it without tracking that state.
    """
    user_id = str(current_user["_id"])
    session = await _get_owned_session(db, session_id, user_id, must_be_active=True)
    _require_identity_gate(session)
    questions = session["questions"]

    at_full_length = len(questions) >= interview_service.QUESTIONS_PER_SESSION
    awaiting_answer = questions and questions[-1].get("content_score") is None
    if at_full_length or awaiting_answer:
        return _to_out(session)

    try:
        questions.append(await interview_service.build_next_question(db, session, user_id))
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    await db.sessions.update_one({"_id": session["_id"]}, {"$set": {"questions": questions}})
    return _to_out(session)


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Finalise a session — the single exit point, whichever way it's reached.

    Ending is the same call whether the candidate finished all questions,
    clicked finish early, or left the page after confirming: the caller never
    has to decide completed-vs-discarded itself, this endpoint does, based on
    how many questions actually got answered. Fewer than
    MIN_ANSWERED_FOR_HISTORY and the session is marked discarded rather than
    completed — no aggregates computed, no summary generated, and it stays
    out of history and the average-score calculation (both key off
    overall_score being set, which discarded sessions never get).
    """
    session = await _get_owned_session(db, session_id, str(current_user["_id"]))

    # Drop a trailing unanswered question so it doesn't distort the report.
    questions = session["questions"]
    if questions and questions[-1].get("content_score") is None:
        questions = questions[:-1]

    answered_count = len(interview_service.answered_scores(questions))
    if answered_count >= interview_service.MIN_ANSWERED_FOR_HISTORY:
        updates = {
            **interview_service.compute_aggregates(questions),
            **await interview_service.summarise(session["role"], questions),
            "questions": questions,
            "status": SessionStatus.completed.value,
            "ended_at": datetime.now(timezone.utc),
        }
    else:
        updates = {
            "questions": questions,
            "status": SessionStatus.discarded.value,
            "ended_at": datetime.now(timezone.utc),
        }

    # Re-read identity rather than using the copy fetched above: summarising
    # takes seconds, and a check landing meanwhile must not be overwritten.
    fresh = await db.sessions.find_one({"_id": session["_id"]}, {"identity": 1})
    if fresh and fresh.get("identity"):
        updates["identity"] = identity_service.finalise(fresh["identity"], updates["ended_at"])
    # The verdict is kept; the face it was reached with is not.
    await identity_service.delete_session_reference(db, session["_id"])

    await db.sessions.update_one({"_id": session["_id"]}, {"$set": updates})
    return _to_out({**session, **updates})


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Everything the report screen needs, in one call.

    The themes were generated when the session ended, so this is a plain read.
    """
    session = await _get_owned_session(db, session_id, str(current_user["_id"]))

    return {
        "session": _to_out(session),
        "strengths": session.get("strengths", []),
        "improvements": session.get("improvements", []),
    }


@router.websocket("/{session_id}/stream")
async def interview_stream(websocket: WebSocket, session_id: str):
    """Live audio/video channel for the real-time interview loop.

    TODO: VAD-based utterance segmentation -> Whisper transcription -> the same
    scoring path as POST /answer, plus sampled video frames through
    cv_analysis. Scoring and adaptation are already implemented in
    interview_service; this endpoint only needs to feed them a live transcript.
    """
    await websocket.accept()
    try:
        await websocket.send_json(
            {
                "type": "not_implemented",
                "detail": "Live streaming lands with the Whisper milestone. "
                "Use POST /sessions/{id}/answer with a transcript meanwhile.",
            }
        )
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
