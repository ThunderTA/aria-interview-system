from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.models.identity import IdentitySummary


class SessionRole(str, Enum):
    sde = "SDE"
    data_scientist = "DS"
    ml_engineer = "MLE"
    qa = "QA"
    product_manager = "PM"
    hr = "HR"


class SessionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"
    discarded = "discarded"


class SessionMode(str, Enum):
    # One question at a time; speak or type each answer.
    classic = "classic"
    # A spoken back-and-forth with follow-up questions.
    conversation = "conversation"


class QuestionAnswer(BaseModel):
    question_id: str
    text: str
    topic: str | None = None
    difficulty_level: int
    order_index: int
    transcript: str | None = None
    wpm: float | None = None
    pause_count: int | None = None
    filler_count: int | None = None
    content_score: float | None = None
    delivery_score: float | None = None
    gaze_score: float | None = None
    expression_score: float | None = None
    posture_score: float | None = None
    feedback_text: str | None = None
    # Rubric breakdown behind content_score (each 0-10), from the LLM judge.
    rubric: dict[str, int] | None = None
    # Pace/filler/pause sub-scores behind delivery_score; spoken answers only.
    delivery_breakdown: dict[str, float] | None = None
    delivery_note: str | None = None
    # Camera-derived; present only when a face was visible in enough frames.
    face_presence: float | None = None
    visual_note: str | None = None
    answered_at: datetime | None = None
    # Conversation mode: when the interviewer moved on. Closed without a
    # content_score means the answer is still being scored.
    closed_at: datetime | None = None


class ConversationTurn(BaseModel):
    id: str
    speaker: Literal["interviewer", "candidate"]
    kind: str
    text: str
    question_index: int | None = None
    at: datetime


class ConversationState(BaseModel):
    phase: Literal["intro", "questioning", "candidate_questions", "closed"]
    turns: list[ConversationTurn] = Field(default_factory=list)


class SessionCreate(BaseModel):
    role: SessionRole
    # 1 (warm-up) to 5 (hard). Omitted or null means "let ARIA decide" —
    # the resume-derived seniority sets the starting point instead.
    starting_difficulty: int | None = Field(default=None, ge=1, le=5)
    mode: SessionMode = SessionMode.classic


class AnswerSubmit(BaseModel):
    """A transcribed answer to the session's current (last) question."""

    transcript: str


class SessionOut(BaseModel):
    id: str
    user_id: str
    role: SessionRole
    mode: SessionMode = SessionMode.classic
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None = None
    overall_score: float | None = None
    content_score_avg: float | None = None
    delivery_score_avg: float | None = None
    visual_score_avg: float | None = None
    questions: list[QuestionAnswer] = Field(default_factory=list)
    conversation: ConversationState | None = None
    # Absent on sessions from before identity verification existed.
    identity: IdentitySummary | None = None


class SessionInDB(BaseModel):
    user_id: str
    role: SessionRole
    mode: SessionMode = SessionMode.classic
    status: SessionStatus = SessionStatus.in_progress
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    overall_score: float | None = None
    content_score_avg: float | None = None
    delivery_score_avg: float | None = None
    visual_score_avg: float | None = None
    questions: list[QuestionAnswer] = Field(default_factory=list)
