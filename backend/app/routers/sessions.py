from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import get_current_user
from app.db.mongodb import get_db
from app.models.session import AnswerSubmit, SessionCreate, SessionOut, SessionStatus
from app.services import interview_service
from app.services.llm_client import LLMUnavailableError

router = APIRouter(prefix="/sessions", tags=["sessions"])


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
    }

    try:
        first_question = await interview_service.build_next_question(db, doc, user_id)
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


@router.post("/{session_id}/answer", response_model=SessionOut)
async def submit_answer(
    session_id: str,
    payload: AnswerSubmit,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Score the answer to the current question, then queue the next one.

    Until the WebSocket + Whisper path lands, the client sends an already
    transcribed answer here; the scoring and adaptation logic is identical
    either way.
    """
    user_id = str(current_user["_id"])
    session = await _get_owned_session(db, session_id, user_id, must_be_active=True)

    current = session["questions"][-1]
    if current.get("content_score") is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question has already been answered.")

    try:
        await interview_service.score_and_advance(db, session, payload.transcript)

        # Queue the next question unless the session has run its length.
        if len(session["questions"]) < interview_service.QUESTIONS_PER_SESSION:
            session["questions"].append(
                await interview_service.build_next_question(db, session, user_id)
            )
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    await db.sessions.update_one(
        {"_id": session["_id"]}, {"$set": {"questions": session["questions"]}}
    )
    return _to_out(session)


@router.post("/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Finalise a session and compute its aggregate scores."""
    session = await _get_owned_session(db, session_id, str(current_user["_id"]))

    # Drop a trailing unanswered question so it doesn't distort the report.
    questions = session["questions"]
    if questions and questions[-1].get("content_score") is None:
        questions = questions[:-1]

    updates = {
        **interview_service.compute_aggregates(questions),
        "questions": questions,
        "status": SessionStatus.completed.value,
        "ended_at": datetime.now(timezone.utc),
    }
    await db.sessions.update_one({"_id": session["_id"]}, {"$set": updates})
    return _to_out({**session, **updates})


@router.get("/{session_id}/report")
async def get_report(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Everything the report screen needs, in one call."""
    session = await _get_owned_session(db, session_id, str(current_user["_id"]))
    questions = session.get("questions", [])

    return {
        "session": _to_out(session),
        **interview_service.collect_feedback(questions),
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
