"""Runs a conversational interview: who speaks next, and what they say.

A session in conversation mode moves through four phases:

  intro                greeting; the candidate introduces themselves
  questioning          each main question is a thread — the candidate answers,
                       and the interviewer follows up (at most
                       conversation_max_follow_ups times), clarifies, or moves on
  candidate_questions  "is there anything you'd like to ask me?"
  closed               closing line; the client then ends the session

When a thread closes it is scored in the background as one answer, so the
interviewer never waits on the rubric. Until that score lands, the next
question's difficulty is chosen from the interviewer's quick 0-10 impression,
kept as `provisional_score`.

Turns live on the session document. Candidate turns carry their delivery and
visual metrics so a thread can be scored across every reply in it; the API
model for a turn leaves those metrics out.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.services import cv_analysis, interview_service, interviewer, speech_metrics
from app.services.asr import Transcript
from app.services.llm_client import LLMUnavailableError

logger = logging.getLogger(__name__)

INTRO, QUESTIONING, CANDIDATE_QUESTIONS, CLOSED = "intro", "questioning", "candidate_questions", "closed"

ROLE_TITLES = {
    "SDE": "software development engineer role",
    "DS": "data scientist role",
    "MLE": "machine learning engineer role",
    "QA": "QA and test engineer role",
    "PM": "product manager role",
    "HR": "HR and behavioural round",
}

GREETING = (
    "Hi {name}, I'm ARIA, and I'll be interviewing you today for the {title}. "
    "We'll go through {count} main questions, and I may ask a follow-up or two along the way. "
    "Take your time with each answer, and just pause for a few seconds when you're done. "
    "To start, could you tell me a little about yourself?"
)
LAST_QUESTION = "That's all the questions I have. Before we wrap up, is there anything you'd like to ask me?"
CLOSING = (
    "Thanks for your time today, {name}. That's the end of the interview, "
    "and your report will be ready in a moment."
)
DIDNT_CATCH = "Sorry, I didn't quite catch that. Could you say it again?"

# What the rubric scorer writes onto a question, persisted field by field so a
# background write never overwrites a turn recorded in the meantime.
_SCORED_FIELDS = (
    "transcript",
    "content_score",
    "rubric",
    "feedback_text",
    "answered_at",
    "wpm",
    "pause_count",
    "filler_count",
    "delivery_score",
    "delivery_breakdown",
    "delivery_note",
    "gaze_score",
    "expression_score",
    "posture_score",
    "face_presence",
    "visual_note",
    "attention",
)

_scoring_locks: dict[str, asyncio.Lock] = {}
# Strong references: asyncio only keeps weak ones, and a collected task stops.
_background_tasks: set[asyncio.Task] = set()


class ConversationClosed(RuntimeError):
    """A turn arrived after the interview wrapped up."""


class ConversationConflict(RuntimeError):
    """Another turn was recorded first, e.g. the same reply submitted twice."""


@dataclass
class TurnOutcome:
    interviewer_turn: dict
    closed: bool


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _turn(speaker: str, kind: str, text: str, question_index: int | None = None, **metrics) -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "speaker": speaker,
        "kind": kind,
        "text": text,
        "question_index": question_index,
        "at": _now(),
        **metrics,
    }


def first_name(user: dict) -> str:
    name = (user.get("name") or "").strip()
    return name.split()[0] if name else "there"


def initial_state(user: dict, role: str) -> dict:
    greeting = GREETING.format(
        name=first_name(user),
        title=ROLE_TITLES.get(role, "role"),
        count=interview_service.QUESTIONS_PER_SESSION,
    )
    return {
        "phase": INTRO,
        "version": 0,
        "follow_ups": 0,
        "clarifications": 0,
        "turns": [_turn("interviewer", "greeting", greeting)],
    }


async def take_turn(
    db: AsyncIOMotorDatabase,
    session: dict,
    user: dict,
    transcript: Transcript | None,
    delivery: dict | None,
    visual: dict | None,
) -> TurnOutcome:
    """Record the candidate's turn and produce the interviewer's reply.

    `transcript` is None when nothing intelligible was heard; the interviewer
    then asks the candidate to repeat themselves and nothing advances.
    Mutates `session` to match what was persisted.
    """
    conversation = session["conversation"]
    if conversation["phase"] == CLOSED:
        raise ConversationClosed()

    questions = session["questions"]
    set_fields: dict = {}

    if transcript is None:
        index = len(questions) - 1 if conversation["phase"] == QUESTIONING else None
        reply = _turn("interviewer", "repeat_request", DIDNT_CATCH, index)
    elif conversation["phase"] == INTRO:
        conversation["turns"].append(_turn("candidate", "introduction", transcript.text))
        acknowledgement = await interviewer.reply_to_introduction(session["role"], transcript.text)
        reply = _turn(
            "interviewer", "question", f"{acknowledgement} Let's get started. {questions[0]['text']}", 0
        )
        conversation.update(phase=QUESTIONING, follow_ups=0, clarifications=0)
    elif conversation["phase"] == QUESTIONING:
        reply = await _continue_thread(db, session, transcript, delivery, visual, set_fields)
    else:
        conversation["turns"].append(_turn("candidate", "question_for_interviewer", transcript.text))
        answer = await interviewer.answer_candidate_question(session["role"], transcript.text)
        reply = _turn("interviewer", "closing", f"{answer} {CLOSING.format(name=first_name(user))}")
        conversation["phase"] = CLOSED

    conversation["turns"].append(reply)
    expected_version = conversation["version"]
    conversation["version"] = expected_version + 1
    set_fields["conversation"] = conversation

    result = await db.sessions.update_one(
        {"_id": session["_id"], "status": "in_progress", "conversation.version": expected_version},
        {"$set": set_fields},
    )
    if result.modified_count == 0:
        raise ConversationConflict()

    if any(key.endswith(".closed_at") for key in set_fields):
        schedule_scoring(db, session["_id"])
    return TurnOutcome(reply, conversation["phase"] == CLOSED)


async def _continue_thread(
    db: AsyncIOMotorDatabase,
    session: dict,
    transcript: Transcript,
    delivery: dict | None,
    visual: dict | None,
    set_fields: dict,
) -> dict:
    conversation = session["conversation"]
    questions = session["questions"]
    index = len(questions) - 1
    question = questions[index]

    candidate = _turn("candidate", "answer", transcript.text, index, delivery=delivery, visual=visual)
    conversation["turns"].append(candidate)
    exchange = [t for t in conversation["turns"] if t.get("question_index") == index]

    move = await interviewer.next_move(
        session["role"],
        question["text"],
        exchange,
        allow_follow_up=conversation["follow_ups"] < settings.conversation_max_follow_ups,
        allow_clarify=conversation["clarifications"] < settings.conversation_max_clarifications,
        follow_ups_asked=conversation["follow_ups"],
    )

    if move["action"] == interviewer.CLARIFY:
        # A question about the question, not an answer to it: kept in the
        # transcript, left out of scoring.
        candidate["kind"] = "clarification_request"
        conversation["clarifications"] += 1
        return _turn("interviewer", "clarification", move["reply"], index)

    if move["action"] == interviewer.FOLLOW_UP:
        conversation["follow_ups"] += 1
        return _turn("interviewer", "follow_up", move["reply"], index)

    question["closed_at"] = _now()
    question["provisional_score"] = move["quality"] * 10.0
    set_fields[f"questions.{index}.closed_at"] = question["closed_at"]
    set_fields[f"questions.{index}.provisional_score"] = question["provisional_score"]

    if len(questions) >= interview_service.QUESTIONS_PER_SESSION:
        conversation["phase"] = CANDIDATE_QUESTIONS
        return _turn("interviewer", "candidate_questions", f"{move['reply']} {LAST_QUESTION}")

    upcoming = await interview_service.build_next_question(db, session, session["user_id"])
    questions.append(upcoming)
    set_fields[f"questions.{index + 1}"] = upcoming
    conversation.update(follow_ups=0, clarifications=0)
    return _turn("interviewer", "question", f"{move['reply']} {upcoming['text']}", index + 1)


# --- Scoring ---------------------------------------------------------------


def schedule_scoring(db: AsyncIOMotorDatabase, session_id) -> None:
    task = asyncio.create_task(_score_in_background(db, session_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _score_in_background(db: AsyncIOMotorDatabase, session_id) -> None:
    try:
        await score_closed_threads(db, session_id, background=True)
    except Exception:
        logger.exception("Background scoring failed for session %s; it will retry at the end", session_id)


async def score_closed_threads(db: AsyncIOMotorDatabase, session_id, *, background: bool) -> None:
    """Score every closed, unscored thread, oldest first.

    Ordered and locked per session because each thread's Q-learning update
    uses the scores of the threads before it.
    """
    lock = _scoring_locks.setdefault(str(session_id), asyncio.Lock())
    async with lock:
        while True:
            session = await db.sessions.find_one({"_id": session_id})
            if session is None:
                return
            index = next(
                (
                    i
                    for i, q in enumerate(session["questions"])
                    if q.get("closed_at") and q.get("content_score") is None and not q.get("scoring_failed")
                ),
                None,
            )
            if index is None or not await _score_thread(db, session, index, background=background):
                return


async def _score_thread(db: AsyncIOMotorDatabase, session: dict, index: int, *, background: bool) -> bool:
    question = session["questions"][index]
    turns = [t for t in session["conversation"]["turns"] if t.get("question_index") == index]
    answers = [t for t in turns if t["speaker"] == "candidate" and t["kind"] == "answer"]

    follow_ups = []
    for position, turn in enumerate(turns):
        if turn["speaker"] == "interviewer" and turn["kind"] == "follow_up":
            reply = next(
                (t for t in turns[position + 1 :] if t["speaker"] == "candidate" and t["kind"] == "answer"),
                None,
            )
            if reply is not None:
                follow_ups.append((turn["text"], reply["text"]))

    delivery = speech_metrics.combine([t.get("delivery") for t in answers])
    if delivery:
        delivery["note"] = speech_metrics.describe(delivery)
    visual = cv_analysis.combine_results([t.get("visual") for t in answers])

    try:
        await interview_service.score_and_advance(
            db,
            session,
            answers[0]["text"] if answers else "",
            delivery=delivery,
            visual=visual,
            index=index,
            follow_ups=follow_ups,
            background=background,
        )
    except LLMUnavailableError:
        logger.warning("Couldn't score question %s of session %s", index, session["_id"])
        if not background:
            # Ending the session: record the failure so it isn't retried forever.
            await db.sessions.update_one(
                {"_id": session["_id"]}, {"$set": {f"questions.{index}.scoring_failed": True}}
            )
        return False

    await db.sessions.update_one(
        {"_id": session["_id"]},
        {"$set": {f"questions.{index}.{field}": question[field] for field in _SCORED_FIELDS if field in question}},
    )
    return True


async def finish(db: AsyncIOMotorDatabase, session: dict) -> None:
    """Close the open thread (if anything was said in it) and score everything.

    Called when the session ends, however it ends. Waits for any background
    scoring still running, so the report never shows a half-scored interview.
    """
    conversation = session.get("conversation") or {}
    questions = session["questions"]
    set_fields: dict = {"conversation.phase": CLOSED}

    index = len(questions) - 1
    answered_open_thread = (
        conversation.get("phase") == QUESTIONING
        and index >= 0
        and questions[index].get("closed_at") is None
        and any(
            t.get("question_index") == index and t["speaker"] == "candidate" and t["kind"] == "answer"
            for t in conversation.get("turns", [])
        )
    )
    if answered_open_thread:
        set_fields[f"questions.{index}.closed_at"] = _now()

    await db.sessions.update_one({"_id": session["_id"]}, {"$set": set_fields})
    await score_closed_threads(db, session["_id"], background=False)
    _scoring_locks.pop(str(session["_id"]), None)
