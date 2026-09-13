from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class IdentityOutcome(str, Enum):
    """Result of looking at one moment of the interview."""

    face_not_detected = "FACE_NOT_DETECTED"
    multiple_faces = "MULTIPLE_FACES_DETECTED"
    match = "IDENTITY_MATCH"
    mismatch = "IDENTITY_MISMATCH"


class IdentityMethod(str, Enum):
    resume_photo = "resume_photo"
    camera = "camera"


class IdentityGate(str, Enum):
    """Whether the candidate has got past the start-of-interview check."""

    pending = "pending"
    verified = "verified"
    # The resume photo never matched and the candidate chose to continue.
    unmatched = "unmatched"
    # Face verification couldn't run at all, and the candidate continued.
    unavailable = "unavailable"


class IdentityEventType(str, Enum):
    persistent_mismatch = "PERSISTENT_MISMATCH"
    multiple_people = "MULTIPLE_PEOPLE"
    start_unmatched = "START_UNMATCHED"
    verification_unavailable = "VERIFICATION_UNAVAILABLE"


class IdentityStatus(str, Enum):
    verified = "verified"
    flagged = "flagged"
    inconclusive = "inconclusive"
    not_verified = "not_verified"


class ResumePhotoOut(BaseModel):
    """What the candidate is told about their resume photo — never the face itself."""

    status: Literal["usable", "not_found", "unusable", "unavailable"]
    reason: str | None = None


class IdentityEvent(BaseModel):
    type: IdentityEventType
    started_at: datetime
    ended_at: datetime | None = None
    checks: int = 0


class IdentityWarning(BaseModel):
    type: IdentityOutcome
    message: str


class IdentitySummary(BaseModel):
    required: bool
    method: IdentityMethod
    # Why camera verification is used instead of the resume photo, if it is.
    method_reason: str | None = None
    gate: IdentityGate
    check_interval_seconds: int
    start_attempts: int = 0
    can_continue_unmatched: bool = False
    verified_at: datetime | None = None
    checks: int = 0
    matches: int = 0
    mismatches: int = 0
    multiple_faces: int = 0
    face_not_detected: int = 0
    events: list[IdentityEvent] = Field(default_factory=list)
    warning: IdentityWarning | None = None
    status: IdentityStatus | None = None
    status_reason: str | None = None


class IdentityVerifyResult(BaseModel):
    passed: bool
    outcome: IdentityOutcome | None = None
    hint: str | None = None
    message: str
    identity: IdentitySummary


class IdentityCheckResult(BaseModel):
    outcome: IdentityOutcome
    hint: str | None = None
    identity: IdentitySummary
