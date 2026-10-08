"""Live attention tracking: what the candidate is showing the camera right now.

A frame arrives every few seconds while the camera is on, separate from the
less frequent identity checks. Each one is classified by cv_analysis from head
orientation plus eye direction, then folded into the counters here.

A single glance away only moves a counter. An unbroken spell of looking
elsewhere opens an episode, which warns the candidate during the interview and
is listed in the report. The identity verdict is never affected.
"""

from datetime import datetime, timezone

from app.core.config import settings
from app.services.cv_analysis import (
    AWAY_PHRASES,
    AWAY_STATES,
    NO_FACE,
    ON_CAMERA,
    STATE_LABELS,
    STATE_REASONS,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def too_soon(state: dict, at: datetime | None = None) -> bool:
    """Whether a check arrived well inside the configured interval.

    Guards the CPU against a client polling faster than it was asked to; the
    frames themselves are cheap, the landmarker is not.
    """
    last = state.get("last_check_at")
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    spacing = max(1.5, settings.attention_check_interval_seconds * 0.5)
    return ((at or _now()) - last).total_seconds() < spacing


def new_state() -> dict:
    return {
        "checks": 0,
        "counts": {},
        "streak": 0,
        "streak_state": None,
        "episodes": [],
        "current": None,
        "last_check_at": None,
    }


def apply_check(state: dict, frame_state: str, at: datetime | None = None) -> None:
    """Fold one live check into the counters and episodes."""
    at = at or _now()
    state["checks"] += 1
    state["counts"][frame_state] = state["counts"].get(frame_state, 0) + 1
    state["current"] = frame_state
    state["last_check_at"] = at

    if frame_state == state["streak_state"]:
        state["streak"] += 1
    else:
        state["streak"] = 1
        state["streak_state"] = frame_state

    open_episode = _open_episode(state)
    if frame_state in AWAY_STATES and state["streak"] >= settings.attention_away_streak_to_flag:
        if open_episode and open_episode["state"] == frame_state:
            open_episode["checks"] += 1
        else:
            if open_episode:
                open_episode["ended_at"] = at
            state["episodes"].append(
                {
                    "state": frame_state,
                    "started_at": at,
                    "ended_at": None,
                    # The whole streak counts, not just the checks since it crossed.
                    "checks": state["streak"],
                }
            )
    elif open_episode:
        open_episode["ended_at"] = at


def _open_episode(state: dict) -> dict | None:
    for episode in reversed(state["episodes"]):
        if episode["ended_at"] is None:
            return episode
    return None


def _episode_out(episode: dict) -> dict:
    return {
        "state": episode["state"],
        "label": STATE_LABELS[episode["state"]],
        "seconds": round(episode["checks"] * settings.attention_check_interval_seconds, 1),
        "started_at": episode["started_at"],
    }


def summary(state: dict) -> dict:
    """The candidate-facing view: where they've been looking, and for how long."""
    checks = state["checks"] or 1
    shares = {
        frame_state: round(100.0 * count / checks, 1)
        for frame_state, count in state["counts"].items()
    }
    current = state.get("current")
    open_episode = _open_episode(state)

    warning = None
    if open_episode:
        state_name = open_episode["state"]
        # "Not in frame - being out of frame" says the same thing twice.
        reason = STATE_REASONS.get(state_name) if state_name != NO_FACE else None
        warning = (
            f"{STATE_LABELS[state_name]} for a while"
            + (f" - {reason}." if reason else ".")
            + " This is noted in your report."
        )

    return {
        "checks": state["checks"],
        "on_camera_share": shares.get(ON_CAMERA, 0.0),
        "shares": shares,
        "current": current,
        "current_label": STATE_LABELS.get(current) if current else None,
        "warning": warning,
        "episodes": [_episode_out(e) for e in state["episodes"]],
        "note": state.get("note"),
    }


def finalise(state: dict, ended_at: datetime) -> dict:
    """Close any open episode and write the session-level line for the report."""
    for episode in state["episodes"]:
        if episode["ended_at"] is None:
            episode["ended_at"] = ended_at

    view = summary(state)
    on_camera = view["on_camera_share"]
    away = {s: share for s, share in view["shares"].items() if s in AWAY_STATES}

    if not state["checks"]:
        state["note"] = None
    elif not away:
        state["note"] = f"You looked at the camera for {on_camera:.0f}% of the interview."
    else:
        worst, share = max(away.items(), key=lambda item: item[1])
        reason = STATE_REASONS.get(worst)
        state["note"] = (
            f"You looked at the camera for {on_camera:.0f}% of the interview. "
            f"You spent {share:.0f}% of the checks {AWAY_PHRASES[worst]}"
            + (f" - {reason}." if reason and worst != "no_face" else ".")
        )
    return state
