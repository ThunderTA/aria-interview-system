"""Candidate identity verification: references, checks, and the verdict.

The flow, end to end:

  resume upload  a usable resume photo becomes an encrypted reference
  session start  method = resume_photo if that reference exists, else camera
  start gate     resume_photo: live frames must match the resume photo
                 camera:       live frames are enrolled as the reference
                 Either way the verified live face is kept as a session
                 anchor, so later checks can compare webcam to webcam.
  during         a frame every identity_check_interval_seconds; one bad frame
                 only moves a counter, a streak of them opens an integrity event
  end            counters become a verdict and the session reference is deleted

The session document only ever holds counters, events and the verdict.
Embeddings live encrypted in `identity_references`, whose TTL index is the
backstop for sessions abandoned without reaching /end.
"""

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.biometric_crypto import decrypt_embedding, encrypt_embedding
from app.core.config import settings
from app.models.identity import (
    IdentityEventType,
    IdentityGate,
    IdentityMethod,
    IdentityOutcome,
    IdentityStatus,
)
from app.models.session import SessionStatus
from app.services import face_identity
from app.services.face_identity import FaceAnalysis, FrameOutcome

REFERENCES = "identity_references"

# Frames the browser sends for the start check, and how many must show a clear face.
START_MIN_GOOD_FRAMES = 2

WARNING_MESSAGES = {
    IdentityOutcome.mismatch: "We couldn't confirm it's still you on camera. This will be noted in your report.",
    IdentityOutcome.multiple_faces: "More than one person appears to be in frame. This will be noted in your report.",
}

START_MESSAGES = {
    "multiple_faces": "More than one face is in view. Make sure only you are in frame, then try again.",
    "too_dark": "It's too dark to see your face clearly. Turn on a light or face a window, then try again.",
    "blurry": "The image is too blurry. Hold still and check the lens is clean, then try again.",
    "too_small": "You're too far from the camera. Move closer so your face fills more of the frame.",
    "hold_still": "Your face moved too much between frames. Hold still, facing the camera, and try again.",
    "no_face": "We couldn't see a face. Centre yourself in the frame and look at the camera.",
    "mismatch": "Face the camera directly in good light, then try again. An old or low-resolution resume photo can also cause this.",
}

EVENT_REASONS = {
    IdentityEventType.start_unmatched: "your face didn't match your resume photo at the start",
    IdentityEventType.persistent_mismatch: "a different face was seen for several checks in a row",
    IdentityEventType.multiple_people: "more than one person was in frame for several checks in a row",
}


class ContinueNotAllowed(RuntimeError):
    """Continuing without a match was requested before it was permitted."""


class ReferenceUnavailable(RuntimeError):
    """The session's reference embedding is gone (expired, or the key changed)."""


class CheckTooSoon(RuntimeError):
    """A periodic check arrived well before the configured interval."""


class EngineStillAvailable(RuntimeError):
    """Skipping was requested, but face verification is working."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """MongoDB hands datetimes back naive; they are always UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


# --- Reference storage -----------------------------------------------------


def _resume_ref_id(user_id: str) -> str:
    return f"resume:{user_id}"


def _session_ref_id(session_id) -> str:
    return f"session:{session_id}"


async def _store_reference(
    db: AsyncIOMotorDatabase, ref_id: str, user_id: str, embedding: np.ndarray, ttl: timedelta
) -> None:
    now = _now()
    await db[REFERENCES].replace_one(
        {"_id": ref_id},
        {
            "_id": ref_id,
            "user_id": user_id,
            "ciphertext": encrypt_embedding(embedding),
            "created_at": now,
            "expires_at": now + ttl,
        },
        upsert=True,
    )


async def _load_reference(db: AsyncIOMotorDatabase, ref_id: str) -> np.ndarray | None:
    doc = await db[REFERENCES].find_one({"_id": ref_id})
    if doc is None or _as_utc(doc["expires_at"]) <= _now():
        return None
    return decrypt_embedding(doc["ciphertext"])


async def store_resume_reference(db: AsyncIOMotorDatabase, user_id: str, embedding: np.ndarray) -> None:
    await _store_reference(
        db,
        _resume_ref_id(user_id),
        user_id,
        embedding,
        timedelta(days=settings.identity_resume_reference_ttl_days),
    )


async def delete_resume_reference(db: AsyncIOMotorDatabase, user_id: str) -> None:
    await db[REFERENCES].delete_one({"_id": _resume_ref_id(user_id)})


async def resume_reference(db: AsyncIOMotorDatabase, user_id: str) -> np.ndarray | None:
    return await _load_reference(db, _resume_ref_id(user_id))


async def delete_session_reference(db: AsyncIOMotorDatabase, session_id) -> None:
    await db[REFERENCES].delete_one({"_id": _session_ref_id(session_id)})


# --- Session state ---------------------------------------------------------


async def initial_state(db: AsyncIOMotorDatabase, user_id: str) -> dict | None:
    """Identity state for a new session, or None when verification is switched off."""
    if not settings.identity_verification_enabled:
        return None

    if await resume_reference(db, user_id) is not None:
        method, reason = IdentityMethod.resume_photo, None
    else:
        resume = await db.resumes.find_one({"user_id": user_id}, {"photo": 1}) or {}
        photo_status = (resume.get("photo") or {}).get("status")
        method = IdentityMethod.camera
        reason = {
            "usable": "photo_reference_unavailable",
            "unusable": "resume_photo_unusable",
            "unavailable": "photo_analysis_unavailable",
        }.get(photo_status, "no_resume_photo")

    return {
        "required": True,
        "method": method.value,
        "method_reason": reason,
        "gate": IdentityGate.pending.value,
        "start_attempts": 0,
        "start_unmatched_attempts": 0,
        "verified_at": None,
        "checks": 0,
        "matches": 0,
        "mismatches": 0,
        "multiple_faces": 0,
        "face_not_detected": 0,
        "mismatch_streak": 0,
        "mismatch_streak_since": None,
        "multi_face_streak": 0,
        "multi_face_streak_since": None,
        "events": [],
        "last_check_at": None,
        "status": None,
        "status_reason": None,
    }


def gate_open(session: dict) -> bool:
    """Whether the candidate may answer questions yet."""
    state = session.get("identity")
    return not (state and state.get("required") and state.get("gate") == IdentityGate.pending.value)


def can_continue_unmatched(state: dict) -> bool:
    return (
        settings.identity_allow_continue_unmatched
        and state["method"] == IdentityMethod.resume_photo.value
        and state["gate"] == IdentityGate.pending.value
        and state["start_unmatched_attempts"] >= settings.identity_start_max_attempts
    )


def _open_event(state: dict, event_type: IdentityEventType) -> dict | None:
    for event in state["events"]:
        if event["type"] == event_type.value and event["ended_at"] is None:
            return event
    return None


def _close_event(state: dict, event_type: IdentityEventType, at: datetime) -> None:
    event = _open_event(state, event_type)
    if event is not None:
        event["ended_at"] = at


def summary(state: dict) -> dict:
    """The candidate-facing view of the state. Contains no biometric data."""
    # Multiple people first: that event closes on the next single-face frame,
    # so if it's open it describes what's in front of the camera right now,
    # whereas a mismatch event stays open through multi-face frames.
    warning = None
    if _open_event(state, IdentityEventType.multiple_people):
        warning = {
            "type": IdentityOutcome.multiple_faces,
            "message": WARNING_MESSAGES[IdentityOutcome.multiple_faces],
        }
    elif _open_event(state, IdentityEventType.persistent_mismatch):
        warning = {"type": IdentityOutcome.mismatch, "message": WARNING_MESSAGES[IdentityOutcome.mismatch]}

    return {
        "required": state["required"],
        "method": state["method"],
        "method_reason": state.get("method_reason"),
        "gate": state["gate"],
        "check_interval_seconds": settings.identity_check_interval_seconds,
        "start_attempts": state["start_attempts"],
        "can_continue_unmatched": can_continue_unmatched(state),
        "verified_at": state.get("verified_at"),
        "checks": state["checks"],
        "matches": state["matches"],
        "mismatches": state["mismatches"],
        "multiple_faces": state["multiple_faces"],
        "face_not_detected": state["face_not_detected"],
        "events": state["events"],
        "warning": warning,
        "status": state.get("status"),
        "status_reason": state.get("status_reason"),
    }


async def _save_state(db: AsyncIOMotorDatabase, session: dict) -> None:
    # Conditional on the session still running: a check that was in flight
    # when /end finalised the verdict must not overwrite it afterwards.
    await db.sessions.update_one(
        {"_id": session["_id"], "status": SessionStatus.in_progress.value},
        {"$set": {"identity": session["identity"]}},
    )


# --- Start gate ------------------------------------------------------------


@dataclass
class StartResult:
    passed: bool
    outcome: IdentityOutcome | None
    hint: str | None
    message: str


def _consistent(embeddings: list[np.ndarray]) -> bool:
    """All frames of the start check show the same face."""
    threshold = settings.identity_camera_match_threshold
    return all(
        face_identity.similarity(a, b) >= threshold
        for i, a in enumerate(embeddings)
        for b in embeddings[i + 1 :]
    )


def _dominant_hint(analyses: list[FaceAnalysis]) -> str:
    hints = [a.hint for a in analyses if a.hint and a.hint != "unreadable_frame"]
    return max(set(hints), key=hints.count) if hints else "no_face"


async def verify_start(
    db: AsyncIOMotorDatabase, session: dict, frames: list[bytes], *, continue_unmatched: bool
) -> StartResult:
    """Run the start-of-interview check on a burst of webcam frames.

    Raises FaceEngineUnavailable if the models can't run, and
    ContinueNotAllowed if continuing without a match isn't permitted yet.
    """
    state = session["identity"]
    user_id = session["user_id"]

    analyses = await asyncio.to_thread(lambda: [face_identity.analyse_frame_bytes(f) for f in frames])
    good = [a.embedding for a in analyses if a.outcome is FrameOutcome.ok]

    def fail(outcome: IdentityOutcome, key: str, *, unmatched: bool = False) -> StartResult:
        state["start_attempts"] += 1
        if unmatched:
            state["start_unmatched_attempts"] += 1
        hint = None if key in ("multiple_faces", "mismatch", "no_face") else key
        return StartResult(False, outcome, hint, START_MESSAGES[key])

    if any(a.outcome is FrameOutcome.multiple_faces for a in analyses):
        result = fail(IdentityOutcome.multiple_faces, "multiple_faces")
    elif len(good) < START_MIN_GOOD_FRAMES:
        result = fail(IdentityOutcome.face_not_detected, _dominant_hint(analyses))
    elif not _consistent(good):
        result = fail(IdentityOutcome.face_not_detected, "hold_still")
    else:
        result = await _match_or_enroll(db, session, good, continue_unmatched=continue_unmatched)
        if result is None:
            result = fail(IdentityOutcome.mismatch, "mismatch", unmatched=True)

    await _save_state(db, session)
    return result


async def _match_or_enroll(
    db: AsyncIOMotorDatabase, session: dict, good: list[np.ndarray], *, continue_unmatched: bool
) -> StartResult | None:
    """Verified or continued result, or None for a mismatch the candidate must retry."""
    state = session["identity"]
    now = _now()
    anchor = face_identity.mean_embedding(good)

    if state["method"] == IdentityMethod.resume_photo.value:
        reference = await resume_reference(db, session["user_id"])
        if reference is None:
            # Expired or undecryptable since the session began: verify by camera instead.
            state["method"] = IdentityMethod.camera.value
            state["method_reason"] = "photo_reference_unavailable"
        else:
            matched = [
                e
                for e in good
                if face_identity.similarity(e, reference) >= settings.identity_resume_match_threshold
            ]
            if len(matched) * 2 <= len(good):
                if not continue_unmatched:
                    return None
                if not can_continue_unmatched(state):
                    raise ContinueNotAllowed()
                await _store_session_anchor(db, session, anchor)
                state["gate"] = IdentityGate.unmatched.value
                state["verified_at"] = now
                state["events"].append(
                    {
                        "type": IdentityEventType.start_unmatched.value,
                        "started_at": now,
                        "ended_at": now,
                        "checks": state["start_attempts"] + 1,
                    }
                )
                state["start_attempts"] += 1
                return StartResult(
                    True,
                    IdentityOutcome.mismatch,
                    None,
                    "Continuing without a resume photo match. This will be noted in your report.",
                )
            anchor = face_identity.mean_embedding(matched)

    await _store_session_anchor(db, session, anchor)
    state["gate"] = IdentityGate.verified.value
    state["verified_at"] = now
    message = (
        "Identity confirmed against your resume photo."
        if state["method"] == IdentityMethod.resume_photo.value
        else "Identity confirmed. We'll keep checking it's you during the interview."
    )
    return StartResult(True, IdentityOutcome.match, None, message)


async def _store_session_anchor(db: AsyncIOMotorDatabase, session: dict, embedding: np.ndarray) -> None:
    await _store_reference(
        db,
        _session_ref_id(session["_id"]),
        session["user_id"],
        embedding,
        timedelta(hours=settings.identity_session_reference_ttl_hours),
    )


async def skip_unavailable(db: AsyncIOMotorDatabase, session: dict) -> None:
    """Let the interview proceed when face verification genuinely can't run."""
    if await asyncio.to_thread(face_identity.is_available):
        raise EngineStillAvailable()
    state = session["identity"]
    now = _now()
    state["gate"] = IdentityGate.unavailable.value
    state["events"].append(
        {
            "type": IdentityEventType.verification_unavailable.value,
            "started_at": now,
            "ended_at": now,
            "checks": 0,
        }
    )
    await _save_state(db, session)


# --- Periodic checks -------------------------------------------------------


async def _check_references(db: AsyncIOMotorDatabase, session: dict) -> list[tuple[np.ndarray, float]]:
    state = session["identity"]
    references = []
    anchor = await _load_reference(db, _session_ref_id(session["_id"]))
    if anchor is not None:
        references.append((anchor, settings.identity_camera_match_threshold))
    # An unmatched start means the resume photo isn't this person's reference.
    if state["method"] == IdentityMethod.resume_photo.value and state["gate"] == IdentityGate.verified.value:
        photo = await resume_reference(db, session["user_id"])
        if photo is not None:
            references.append((photo, settings.identity_resume_match_threshold))
    return references


def classify(analysis: FaceAnalysis, references: list[tuple[np.ndarray, float]]) -> tuple[IdentityOutcome, str | None]:
    if analysis.outcome is FrameOutcome.multiple_faces:
        return IdentityOutcome.multiple_faces, None
    if analysis.outcome is not FrameOutcome.ok:
        # A face too dark, blurred or distant to embed reliably is treated as
        # not seen - guessing an identity from it would manufacture mismatches.
        return IdentityOutcome.face_not_detected, analysis.hint
    if any(face_identity.similarity(analysis.embedding, ref) >= t for ref, t in references):
        return IdentityOutcome.match, None
    return IdentityOutcome.mismatch, None


def apply_check(state: dict, outcome: IdentityOutcome, at: datetime) -> None:
    """Fold one check into the counters, streaks and integrity events.

    Only a match ends a mismatch streak and only a single visible face ends a
    multiple-face streak; a frame with no face leaves both where they were, so
    covering the camera between bad frames can't reset them.
    """
    state["checks"] += 1
    state["last_check_at"] = at

    if outcome is IdentityOutcome.face_not_detected:
        state["face_not_detected"] += 1
        return

    if outcome is IdentityOutcome.multiple_faces:
        state["multiple_faces"] += 1
        state["multi_face_streak"] += 1
        state["multi_face_streak_since"] = state["multi_face_streak_since"] or at
        _extend_or_open(
            state,
            IdentityEventType.multiple_people,
            state["multi_face_streak"],
            settings.identity_multi_face_streak_to_flag,
            state["multi_face_streak_since"],
        )
        return

    # A single face was seen: whatever the multiple-face streak was, it's over.
    state["multi_face_streak"] = 0
    state["multi_face_streak_since"] = None
    _close_event(state, IdentityEventType.multiple_people, at)

    if outcome is IdentityOutcome.match:
        state["matches"] += 1
        state["mismatch_streak"] = 0
        state["mismatch_streak_since"] = None
        _close_event(state, IdentityEventType.persistent_mismatch, at)
    else:
        state["mismatches"] += 1
        state["mismatch_streak"] += 1
        state["mismatch_streak_since"] = state["mismatch_streak_since"] or at
        _extend_or_open(
            state,
            IdentityEventType.persistent_mismatch,
            state["mismatch_streak"],
            settings.identity_mismatch_streak_to_flag,
            state["mismatch_streak_since"],
        )


def _extend_or_open(state: dict, event_type: IdentityEventType, streak: int, threshold: int, since: datetime) -> None:
    event = _open_event(state, event_type)
    if event is not None:
        event["checks"] += 1
    elif streak >= threshold:
        state["events"].append({"type": event_type.value, "started_at": since, "ended_at": None, "checks": streak})


async def run_check(db: AsyncIOMotorDatabase, session: dict, frame: bytes | None) -> tuple[IdentityOutcome, str | None]:
    """One periodic check. `frame` is None when the candidate's camera is off.

    Raises CheckTooSoon, ReferenceUnavailable or FaceEngineUnavailable; none of
    those count as a check, since none of them say anything about the candidate.
    """
    state = session["identity"]
    now = _now()

    last = _as_utc(state.get("last_check_at"))
    min_spacing = max(2.0, settings.identity_check_interval_seconds * 0.4)
    if last is not None and (now - last).total_seconds() < min_spacing:
        raise CheckTooSoon()

    if frame is None:
        outcome, hint = IdentityOutcome.face_not_detected, "camera_off"
    else:
        references = await _check_references(db, session)
        if not references:
            raise ReferenceUnavailable()
        analysis = await asyncio.to_thread(face_identity.analyse_frame_bytes, frame)
        outcome, hint = classify(analysis, references)

    apply_check(state, outcome, now)
    await _save_state(db, session)
    return outcome, hint


# --- Verdict ---------------------------------------------------------------


def finalise(state: dict, ended_at: datetime) -> dict:
    """Close open events and turn the counters into an overall status."""
    if state.get("status") is not None:
        return state

    for event in state["events"]:
        if event["ended_at"] is None:
            event["ended_at"] = ended_at

    gate = state["gate"]
    checks = state["checks"]
    matches, mismatches = state["matches"], state["mismatches"]
    conclusive = matches + mismatches

    if gate == IdentityGate.pending.value:
        status, reason = IdentityStatus.not_verified, "The session ended before identity was confirmed."
    elif gate == IdentityGate.unavailable.value:
        status, reason = IdentityStatus.not_verified, "Face verification was unavailable, so identity couldn't be checked."
    else:
        flagged = [
            EVENT_REASONS[IdentityEventType(t)]
            for t in dict.fromkeys(e["type"] for e in state["events"])
            if IdentityEventType(t) in EVENT_REASONS
        ]
        verified_at = _as_utc(state.get("verified_at")) or ended_at
        expected = int((ended_at - verified_at).total_seconds() // settings.identity_check_interval_seconds)
        coverage = checks / expected if expected > 0 else 1.0

        if flagged:
            status = IdentityStatus.flagged
            reason = "Flagged because " + "; ".join(flagged) + "."
        elif conclusive < settings.identity_min_conclusive_checks:
            status, reason = IdentityStatus.inconclusive, "Too few checks saw a clear face to confirm identity."
        elif expected >= settings.identity_min_conclusive_checks and coverage < settings.identity_min_check_coverage:
            status = IdentityStatus.inconclusive
            reason = "Identity checks stopped for much of the session - the camera was off or checks were interrupted."
        elif state["face_not_detected"] * 2 > checks:
            status, reason = IdentityStatus.inconclusive, "Your face wasn't visible for most of the checks."
        elif matches / conclusive < settings.identity_verified_min_match_rate:
            status = IdentityStatus.inconclusive
            reason = f"Identity matched in only {math.floor(100 * matches / conclusive)}% of checks with a clear face."
        else:
            status, reason = IdentityStatus.verified, f"Matched in {matches} of {conclusive} checks with a clear face."

    state["status"] = status.value
    state["status_reason"] = reason
    return state
