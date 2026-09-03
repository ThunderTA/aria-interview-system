from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class SessionRole(str, Enum):
    sde = "SDE"
    hr = "HR"


class SessionStatus(str, Enum):
    in_progress = "in_progress"
    completed = "completed"
    discarded = "discarded"


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


class SessionCreate(BaseModel):
    role: SessionRole


class AnswerSubmit(BaseModel):
    """A transcribed answer to the session's current (last) question."""

    transcript: str


class SessionOut(BaseModel):
    id: str
    user_id: str
    role: SessionRole
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None = None
    overall_score: float | None = None
    content_score_avg: float | None = None
    delivery_score_avg: float | None = None
    visual_score_avg: float | None = None
    questions: list[QuestionAnswer] = Field(default_factory=list)


class SessionInDB(BaseModel):
    user_id: str
    role: SessionRole
    status: SessionStatus = SessionStatus.in_progress
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: datetime | None = None
    overall_score: float | None = None
    content_score_avg: float | None = None
    delivery_score_avg: float | None = None
    visual_score_avg: float | None = None
    questions: list[QuestionAnswer] = Field(default_factory=list)
