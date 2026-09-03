"""Visual analysis of the candidate during an answer.

Runs MediaPipe's FaceLandmarker over frames sampled from the webcam (~1-2 fps,
not full frame rate — gaze and posture don't change meaningfully between
frames, and the extra compute buys nothing).

Produces three scores, each 0-100:
  gaze        how much of the answer was spent looking at the camera
  expression  visible engagement — eyes open, face animated, not fixed in a
              frown. Deliberately NOT an emotion classifier; inferring felt
              emotion from a face is not reliable enough to grade someone on.
  posture     head steadiness and level framing, i.e. not drifting out of
              frame or tilting heavily. Head posture only, since a webcam
              headshot rarely shows enough body to judge more.

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

# Head rotation away from the camera, in degrees, still counted as "looking at
# the interviewer". Generous on yaw: people naturally glance sideways while
# thinking, and a narrow cone would punish normal behaviour.
YAW_TOLERANCE_DEG = 22.0
PITCH_TOLERANCE_DEG = 18.0

# Head roll beyond this reads as a tilted/slouched head rather than level.
ROLL_TOLERANCE_DEG = 12.0

# Fraction of frames with a face visible below which we assume the candidate
# was out of frame rather than merely looking away.
MIN_FACE_PRESENCE = 0.5

# Blendshape names used for the expression score.
EYE_BLINK_SHAPES = ("eyeBlinkLeft", "eyeBlinkRight")
FROWN_SHAPES = ("browDownLeft", "browDownRight")
SMILE_SHAPES = ("mouthSmileLeft", "mouthSmileRight")

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
    logger.info("Downloading MediaPipe face landmarker model…")
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


def euler_from_matrix(matrix: np.ndarray) -> tuple[float, float, float]:
    """Head yaw, pitch and roll in degrees from the 4x4 facial transform.

    Standard ZYX extraction; the gimbal-lock branch matters because a candidate
    looking sharply down is exactly the degenerate case.
    """
    r = np.asarray(matrix)[:3, :3]
    sy = math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)

    if sy > 1e-6:
        pitch = math.atan2(-r[2, 0], sy)
        yaw = math.atan2(r[1, 0], r[0, 0])
        roll = math.atan2(r[2, 1], r[2, 2])
    else:
        pitch = math.atan2(-r[2, 0], sy)
        yaw = 0.0
        roll = math.atan2(-r[1, 2], r[1, 1])

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def _blendshape_value(blendshapes, *names: str) -> float:
    """Mean score of the named blendshapes, 0 if none are present."""
    if not blendshapes:
        return 0.0
    wanted = {n.lower() for n in names}
    values = [c.score for c in blendshapes if c.category_name.lower() in wanted]
    return float(np.mean(values)) if values else 0.0


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

    yaw = pitch = roll = 0.0
    if result.facial_transformation_matrixes:
        yaw, pitch, roll = euler_from_matrix(result.facial_transformation_matrixes[0])

    # Nose tip (landmark 1) as a proxy for where the head sits in frame.
    nose = landmarks[1]

    return {
        "yaw": yaw,
        "pitch": pitch,
        "roll": roll,
        "centre_x": nose.x,
        "centre_y": nose.y,
        "eye_closed": _blendshape_value(blendshapes, *EYE_BLINK_SHAPES),
        "frown": _blendshape_value(blendshapes, *FROWN_SHAPES),
        "smile": _blendshape_value(blendshapes, *SMILE_SHAPES),
    }


def _gaze_score(frames: list[dict]) -> float:
    """Share of frames where the head was oriented towards the camera."""
    if not frames:
        return 0.0
    on_camera = sum(
        1
        for f in frames
        if abs(f["yaw"]) <= YAW_TOLERANCE_DEG and abs(f["pitch"]) <= PITCH_TOLERANCE_DEG
    )
    return 100.0 * on_camera / len(frames)


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
        np.mean([1.0 if abs(f["roll"]) <= ROLL_TOLERANCE_DEG else 0.0 for f in frames])
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

    return {
        "gaze_score": round(gaze, 1),
        "expression_score": round(expression, 1),
        "posture_score": round(posture, 1),
        "face_presence": round(presence * 100, 1),
        "frames_analysed": len(analysed),
        "note": _describe(gaze, presence),
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
