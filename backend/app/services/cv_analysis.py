"""Visual analysis of the candidate during an answer.

Runs MediaPipe's FaceLandmarker over frames sampled from the webcam (~1-2 fps,
not full frame rate - gaze and posture don't change meaningfully between
frames, and the extra compute buys nothing).

Produces three scores, each 0-100:
  gaze        how much of the answer was spent looking at the camera
  expression  visible engagement - eyes open, face animated, not fixed in a
              frown. Deliberately NOT an emotion classifier; inferring felt
              emotion from a face is not reliable enough to grade someone on.
  posture     head steadiness and level framing, i.e. not drifting out of
              frame or tilting heavily. Head posture only, since a webcam
              headshot rarely shows enough body to judge more.

Plus an attention breakdown: which way the candidate was looking, and for how
long. Gaze is head orientation combined with eye direction, not head alone: a
head turned 20 degrees away with the eyes back on the lens is eye contact,
which a head-only measure records as none.

All processing is local and frames are discarded immediately after analysis;
nothing visual is persisted, matching the proposal's data commitments.
"""

# Must precede the mediapipe import: on macOS the face-detection subgraph
# otherwise tries to initialise Metal and aborts the process. GPU buys nothing
# at this frame rate, so disabling it removes a platform-specific crash.
import os

os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")
os.environ.setdefault("GLOG_minloglevel", "2")

import asyncio  # noqa: E402
import io  # noqa: E402
import logging  # noqa: E402
import math  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_PATH = Path.home() / ".cache" / "aria" / "models" / "face_landmarker.task"

# --- Thresholds, documented so they can be defended and tuned -------------

# How far the gaze may stray from the lens and still count as eye contact.
# Generous horizontally: people glance sideways while thinking, and a narrow
# cone would punish normal behaviour.
ON_CAMERA_H_DEG = 20.0
ON_CAMERA_V_DEG = 16.0

# A head turned this far is looking away whatever the eyes are doing.
TURNED_AWAY_DEG = 45.0

# Eyes fully deflected in their sockets move the gaze about this far. Used to
# add eye direction to head orientation; the two together are the gaze.
EYE_OFFSET_DEG = 25.0

# Mean blink blendshape above which the eyes are closed rather than narrowed.
EYES_CLOSED_BLINK = 0.5

# Head tipped towards a shoulder beyond this reads as slouched, not level.
TILT_TOLERANCE_DEG = 12.0

# Fraction of frames with a face visible below which we assume the candidate
# was out of frame rather than merely looking away.
MIN_FACE_PRESENCE = 0.5

# Frames arrive about once a second, so one frame is about one second of the
# answer - enough to report "you looked down for six seconds" honestly.
FRAME_SECONDS = 1.0
# A glance is not a distraction; only a run this long is worth reporting.
AWAY_EPISODE_SECONDS = 3.0

# Blendshape names used for the expression and gaze signals.
EYE_BLINK_SHAPES = ("eyeBlinkLeft", "eyeBlinkRight")
FROWN_SHAPES = ("browDownLeft", "browDownRight")
SMILE_SHAPES = ("mouthSmileLeft", "mouthSmileRight")
EYE_UP_SHAPES = ("eyeLookUpLeft", "eyeLookUpRight")
EYE_DOWN_SHAPES = ("eyeLookDownLeft", "eyeLookDownRight")

# --- Attention states ------------------------------------------------------

ON_CAMERA = "on_camera"
LOOKING_LEFT = "looking_left"
LOOKING_RIGHT = "looking_right"
LOOKING_DOWN = "looking_down"
LOOKING_UP = "looking_up"
TURNED_AWAY = "turned_away"
EYES_CLOSED = "eyes_closed"
NO_FACE = "no_face"

STATE_LABELS = {
    ON_CAMERA: "Looking at the camera",
    LOOKING_LEFT: "Looking away to your left",
    LOOKING_RIGHT: "Looking away to your right",
    LOOKING_DOWN: "Looking down",
    LOOKING_UP: "Looking up",
    TURNED_AWAY: "Turned away from the camera",
    EYES_CLOSED: "Eyes closed",
    NO_FACE: "Not in frame",
}

# What a sustained spell of each state usually means. Hedged on purpose: the
# camera can see where someone looked, not why.
STATE_REASONS = {
    LOOKING_LEFT: "a second screen or notes to your left",
    LOOKING_RIGHT: "a second screen or notes to your right",
    LOOKING_DOWN: "notes, a phone or the keyboard",
    LOOKING_UP: "thinking, though it reads as distracted on camera",
    TURNED_AWAY: "something beside you",
    EYES_CLOSED: "eyes closed",
    NO_FACE: "being out of frame",
}

AWAY_STATES = (LOOKING_LEFT, LOOKING_RIGHT, LOOKING_DOWN, LOOKING_UP, TURNED_AWAY, NO_FACE)

_landmarker = None
_landmarker_lock = asyncio.Lock()


class VisualAnalysisError(RuntimeError):
    """Frames could not be analysed."""


def _ensure_model() -> Path:
    """Download the landmarker bundle on first use, like Whisper's weights."""
    if MODEL_PATH.exists():
        return MODEL_PATH

    import urllib.request

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading MediaPipe face landmarker model...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception as exc:  # pragma: no cover - network dependent
        raise VisualAnalysisError(
            "Could not download the face analysis model. Check your connection, "
            "or camera analysis will stay unavailable."
        ) from exc
    return MODEL_PATH


async def _get_landmarker():
    global _landmarker
    if _landmarker is not None:
        return _landmarker

    async with _landmarker_lock:
        if _landmarker is None:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            model_path = await asyncio.to_thread(_ensure_model)
            _landmarker = await asyncio.to_thread(
                vision.FaceLandmarker.create_from_options,
                vision.FaceLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                    running_mode=vision.RunningMode.IMAGE,
                    num_faces=1,
                    output_face_blendshapes=True,
                    output_facial_transformation_matrixes=True,
                ),
            )
            logger.info("Face landmarker ready")
    return _landmarker


async def warm_up() -> None:
    """Pre-load so the first candidate doesn't wait for model download/init."""
    try:
        await _get_landmarker()
    except Exception:
        logger.exception("Face landmarker warm-up failed; it will load on first use")


def head_angles(matrix: np.ndarray) -> tuple[float, float, float]:
    """Head turn, nod and tilt in degrees from the 4x4 facial transform.

    A ZYX extraction, with each axis checked against real frames rather than
    assumed: mirroring a frame flips the Y rotation and leaves X alone, and
    rotating a frame in its own plane moves only the Z rotation. So

        turn (Y)  left/right; positive when the candidate looks to their left
        nod  (X)  up/down; positive when the chin drops towards the chest
        tilt (Z)  head tipped towards a shoulder, in the plane of the image

    The gimbal-lock branch matters because a candidate looking sharply down is
    exactly the degenerate case.
    """
    r = np.asarray(matrix)[:3, :3]
    sy = math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)

    turn = math.atan2(-r[2, 0], sy)
    if sy > 1e-6:
        nod = math.atan2(r[2, 1], r[2, 2])
        tilt = math.atan2(r[1, 0], r[0, 0])
    else:
        nod = math.atan2(-r[1, 2], r[1, 1])
        tilt = 0.0

    return math.degrees(turn), math.degrees(nod), math.degrees(tilt)


def _blendshape_value(blendshapes, *names: str) -> float:
    """Mean score of the named blendshapes, 0 if none are present."""
    if not blendshapes:
        return 0.0
    wanted = {n.lower() for n in names}
    values = [c.score for c in blendshapes if c.category_name.lower() in wanted]
    return float(np.mean(values)) if values else 0.0


def eye_direction(blendshapes) -> tuple[float, float]:
    """Where the eyes point within their sockets, each roughly -1..1.

    Horizontal is positive towards the candidate's left, matching `turn`.
    ARKit's blendshape naming is per-eye and anatomical, so the left eye
    looking "in" (towards the nose) means looking to the candidate's right.
    """
    towards_left = _blendshape_value(blendshapes, "eyeLookOutLeft") + _blendshape_value(
        blendshapes, "eyeLookInRight"
    )
    towards_right = _blendshape_value(blendshapes, "eyeLookInLeft") + _blendshape_value(
        blendshapes, "eyeLookOutRight"
    )
    vertical = _blendshape_value(blendshapes, *EYE_UP_SHAPES) - _blendshape_value(
        blendshapes, *EYE_DOWN_SHAPES
    )
    return (towards_left - towards_right) / 2.0, vertical


def classify_gaze(turn: float, nod: float, eye_h: float, eye_v: float, eye_closed: float) -> dict:
    """Which way the candidate is looking, from head orientation plus eyes."""
    if eye_closed >= EYES_CLOSED_BLINK:
        return {"state": EYES_CLOSED, "gaze_h": 0.0, "gaze_v": 0.0}

    gaze_h = turn + eye_h * EYE_OFFSET_DEG
    gaze_v = eye_v * EYE_OFFSET_DEG - nod

    if abs(turn) >= TURNED_AWAY_DEG:
        state = TURNED_AWAY
    elif abs(gaze_h) <= ON_CAMERA_H_DEG and abs(gaze_v) <= ON_CAMERA_V_DEG:
        state = ON_CAMERA
    # Whichever axis is further outside its tolerance is the one worth naming.
    elif abs(gaze_h) - ON_CAMERA_H_DEG >= abs(gaze_v) - ON_CAMERA_V_DEG:
        state = LOOKING_LEFT if gaze_h > 0 else LOOKING_RIGHT
    else:
        state = LOOKING_UP if gaze_v > 0 else LOOKING_DOWN

    return {"state": state, "gaze_h": round(gaze_h, 1), "gaze_v": round(gaze_v, 1)}


def analyse_frame(image_bytes: bytes, landmarker) -> dict | None:
    """Analyse one frame. Returns None when no face is visible."""
    import mediapipe as mp
    from PIL import Image

    try:
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        return None

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(pil))
    result = landmarker.detect(mp_image)
    if not result.face_landmarks:
        return None

    landmarks = result.face_landmarks[0]
    blendshapes = result.face_blendshapes[0] if result.face_blendshapes else None

    turn = nod = tilt = 0.0
    if result.facial_transformation_matrixes:
        turn, nod, tilt = head_angles(result.facial_transformation_matrixes[0])

    eye_closed = _blendshape_value(blendshapes, *EYE_BLINK_SHAPES)
    eye_h, eye_v = eye_direction(blendshapes)
    gaze = classify_gaze(turn, nod, eye_h, eye_v, eye_closed)

    # Nose tip (landmark 1) as a proxy for where the head sits in frame.
    nose = landmarks[1]

    return {
        "turn": turn,
        "nod": nod,
        "tilt": tilt,
        "centre_x": nose.x,
        "centre_y": nose.y,
        "eye_closed": eye_closed,
        "frown": _blendshape_value(blendshapes, *FROWN_SHAPES),
        "smile": _blendshape_value(blendshapes, *SMILE_SHAPES),
        **gaze,
    }


def _gaze_score(frames: list[dict]) -> float:
    """Share of frames where the candidate was looking at the camera."""
    if not frames:
        return 0.0
    return 100.0 * sum(1 for f in frames if f["state"] == ON_CAMERA) / len(frames)


def _expression_score(frames: list[dict]) -> float:
    """Visible engagement, not emotion.

    Rewards keeping the eyes open and showing some animation; penalises a fixed
    frown. Deliberately shallow, because anything deeper would be claiming to
    read feelings off a face.
    """
    if not frames:
        return 0.0

    eyes_open = 100.0 * (1.0 - min(1.0, float(np.mean([f["eye_closed"] for f in frames])) * 2))
    frown = float(np.mean([f["frown"] for f in frames]))
    frown_penalty = min(40.0, frown * 80)

    # Some variation in the face over the answer reads as engaged rather than
    # frozen; a completely static face scores lower.
    animation = float(np.std([f["smile"] for f in frames])) if len(frames) > 1 else 0.0
    animation_bonus = min(15.0, animation * 150)

    return max(0.0, min(100.0, eyes_open - frown_penalty + animation_bonus))


def _posture_score(frames: list[dict]) -> float:
    """Head kept level and steady, and stays in frame."""
    if not frames:
        return 0.0

    level = 100.0 * float(
        np.mean([1.0 if abs(f["tilt"]) <= TILT_TOLERANCE_DEG else 0.0 for f in frames])
    )

    # Drift of the head around the frame across the answer.
    if len(frames) > 1:
        drift = float(
            np.std([f["centre_x"] for f in frames]) + np.std([f["centre_y"] for f in frames])
        )
        steadiness = max(0.0, 100.0 - drift * 400)
    else:
        steadiness = 100.0

    return round(level * 0.6 + steadiness * 0.4, 1)


# --- Attention -------------------------------------------------------------


def _runs(states: list[str]):
    """Consecutive runs of the same state, as (state, length) pairs."""
    if not states:
        return
    current, length = states[0], 1
    for state in states[1:]:
        if state == current:
            length += 1
        else:
            yield current, length
            current, length = state, 1
    yield current, length


def attention_breakdown(states: list[str], seconds_per_state: float = FRAME_SECONDS) -> dict:
    """Where the candidate looked across a stretch of frames, and for how long."""
    if not states:
        return {"on_camera_share": 0.0, "shares": {}, "episodes": [], "note": None}

    shares = {
        state: round(100.0 * states.count(state) / len(states), 1) for state in dict.fromkeys(states)
    }
    episodes = [
        {
            "state": state,
            "label": STATE_LABELS[state],
            "seconds": round(length * seconds_per_state, 1),
        }
        for state, length in _runs(states)
        if state in AWAY_STATES and length * seconds_per_state >= AWAY_EPISODE_SECONDS
    ]
    breakdown = {
        "on_camera_share": shares.get(ON_CAMERA, 0.0),
        "shares": shares,
        "episodes": episodes,
    }
    breakdown["note"] = describe_attention(breakdown)
    return breakdown


# How each state reads mid-sentence, e.g. "18% was spent looking down".
AWAY_PHRASES = {
    LOOKING_LEFT: "looking away to your left",
    LOOKING_RIGHT: "looking away to your right",
    LOOKING_DOWN: "looking down",
    LOOKING_UP: "looking up",
    TURNED_AWAY: "turned away from the camera",
    EYES_CLOSED: "with your eyes closed",
    NO_FACE: "out of frame",
}


def describe_attention(breakdown: dict) -> str:
    """One plain line about where the candidate was looking."""
    shares = breakdown["shares"]
    on_camera = breakdown["on_camera_share"]
    away = {state: share for state, share in shares.items() if state in AWAY_STATES}

    if not away:
        return f"You looked at the camera for {on_camera:.0f}% of this answer."

    state, share = max(away.items(), key=lambda item: item[1])
    reason = STATE_REASONS.get(state)
    sentence = (
        f"You looked at the camera for {on_camera:.0f}% of this answer; "
        f"{share:.0f}% was spent {AWAY_PHRASES[state]}"
        + (f" ({reason})." if reason and state != NO_FACE else ".")
    )
    longest = max((e["seconds"] for e in breakdown["episodes"]), default=0.0)
    if longest:
        sentence += f" The longest stretch away was about {longest:.0f} seconds."
    return sentence


async def analyse_frames(frames: list[bytes]) -> dict | None:
    """Aggregate visual scores across the frames sampled during one answer.

    Returns None when there were too few usable frames to say anything, so the
    report can stay honestly blank rather than showing an invented score.
    """
    if not frames:
        return None

    landmarker = await _get_landmarker()
    analysed = await asyncio.to_thread(
        lambda: [analyse_frame(f, landmarker) for f in frames]
    )
    visible = [f for f in analysed if f is not None]

    presence = len(visible) / len(analysed) if analysed else 0.0
    if presence < MIN_FACE_PRESENCE or not visible:
        logger.info("Face visible in only %.0f%% of frames; skipping visual scores", presence * 100)
        return None

    gaze = _gaze_score(visible)
    expression = _expression_score(visible)
    posture = _posture_score(visible)
    # Frames without a face count as time out of frame rather than being dropped.
    attention = attention_breakdown([f["state"] if f else NO_FACE for f in analysed])

    return {
        "gaze_score": round(gaze, 1),
        "expression_score": round(expression, 1),
        "posture_score": round(posture, 1),
        "face_presence": round(presence * 100, 1),
        "frames_analysed": len(analysed),
        "attention": attention,
        "note": _describe(gaze, presence),
    }


async def analyse_live_frame(frame: bytes) -> str:
    """The attention state of a single frame, for the live readout."""
    landmarker = await _get_landmarker()
    result = await asyncio.to_thread(analyse_frame, frame, landmarker)
    return result["state"] if result else NO_FACE


def combine_results(results: list[dict | None]) -> dict | None:
    """Visual scores across several answers' frames, weighted by how many frames each had."""
    usable = [r for r in results if r]
    if not usable:
        return None
    total = sum(r["frames_analysed"] for r in usable)

    def weighted(key: str) -> float:
        return round(sum(r[key] * r["frames_analysed"] for r in usable) / total, 1)

    gaze, presence = weighted("gaze_score"), weighted("face_presence")
    shares: dict[str, float] = {}
    episodes: list[dict] = []
    for result in usable:
        attention = result.get("attention") or {}
        weight = result["frames_analysed"] / total
        for state, share in attention.get("shares", {}).items():
            shares[state] = round(shares.get(state, 0.0) + share * weight, 1)
        episodes.extend(attention.get("episodes", []))

    combined_attention = {
        "on_camera_share": shares.get(ON_CAMERA, 0.0),
        "shares": shares,
        "episodes": episodes,
    }
    combined_attention["note"] = describe_attention(combined_attention)

    return {
        "gaze_score": gaze,
        "expression_score": weighted("expression_score"),
        "posture_score": weighted("posture_score"),
        "face_presence": presence,
        "frames_analysed": total,
        "attention": combined_attention,
        "note": _describe(gaze, presence / 100),
    }


def _describe(gaze: float, presence: float) -> str:
    """One plain line about visual presence, for the report."""
    if presence < 0.8:
        return f"You were out of frame for part of this answer ({presence * 100:.0f}% visible)."
    if gaze >= 80:
        return f"You held eye contact well ({gaze:.0f}% of the time)."
    if gaze >= 55:
        return f"You looked away fairly often ({gaze:.0f}% eye contact)."
    return f"You rarely looked at the camera ({gaze:.0f}% eye contact)."
