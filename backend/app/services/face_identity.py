"""Face detection and face embeddings for candidate identity verification.

Two models from OpenCV's model zoo, run through OpenCV's DNN module - already
installed as a MediaPipe dependency, so this adds no new package:

  YuNet  face_detection_yunet_2023mar    finds faces and five landmarks
  SFace  face_recognition_sface_2021dec  maps an aligned face to a 128-d
         embedding; photos of the same person point the same way, so identity
         is compared by cosine similarity rather than by pixels

MediaPipe (cv_analysis.py) isn't reused: its landmarker describes where a face
is and how it moves, but produces nothing that identifies whose face it is.

Images arrive as bytes, are decoded in memory and never written to disk; the
embeddings returned here are handed to identity_service, which encrypts them.
"""

import asyncio
import io
import logging
import threading
import time
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings
from app.services.model_download import ModelDownloadError, ensure_model_file

logger = logging.getLogger(__name__)

try:
    # OpenCV 5 logs a harmless DNN-backend warning on every model load.
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except AttributeError:  # pragma: no cover - older builds
    pass

MODEL_DIR = Path.home() / ".cache" / "aria" / "models"
_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
# Pinned by SHA-256: these are executable model graphs fetched over the network.
_MODELS = {
    "detector": (
        "face_detection_yunet_2023mar.onnx",
        f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "recognizer": (
        "face_recognition_sface_2021dec.onnx",
        f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}
DOWNLOAD_TIMEOUT_SECONDS = 60
# After a failed load, don't retry the download on every request.
RETRY_AFTER_FAILURE_SECONDS = 60

MAX_ANALYSIS_SIDE = 1280
MAX_IMAGE_PIXELS = 40_000_000
# Embedded images smaller than this are icons, bullets or rules, not photos.
MIN_RESUME_IMAGE_SIDE = 48
MAX_RESUME_IMAGE_ASPECT = 4.0
# Small embedded photos are enlarged so the detector has enough pixels to work
# with; the face-size check still measures the original resolution.
DETECTION_MIN_SIDE = 320
MAX_RESUME_IMAGES = 25
MAX_RESUME_PDF_PAGES = 3
MAX_DOCX_MEDIA_BYTES = 10 * 1024 * 1024
DOCX_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}


class FaceEngineUnavailable(RuntimeError):
    """The face models couldn't be downloaded or loaded."""


class FrameOutcome(str, Enum):
    no_face = "no_face"
    multiple_faces = "multiple_faces"
    low_quality = "low_quality"
    ok = "ok"


@dataclass
class FaceAnalysis:
    outcome: FrameOutcome
    # too_dark / blurry / too_small / unreadable_frame - shown as guidance.
    hint: str | None = None
    # Width of the face in source pixels, used to pick the best resume photo.
    face_px: float = 0.0
    embedding: np.ndarray | None = field(default=None, repr=False)


class PhotoStatus(str, Enum):
    usable = "usable"
    not_found = "not_found"
    unusable = "unusable"
    unavailable = "unavailable"


@dataclass
class ResumePhoto:
    status: PhotoStatus
    reason: str | None = None
    embedding: np.ndarray | None = field(default=None, repr=False)

    def public(self) -> dict:
        return {"status": self.status.value, "reason": self.reason}


# --- Model loading ---------------------------------------------------------

_detector = None
_recognizer = None
_last_failure_at = 0.0
_load_lock = threading.Lock()
# Both models keep per-call state (the detector's input size), so inference
# is serialised. At one frame per candidate every few seconds this never binds.
_infer_lock = threading.Lock()


def _ensure_model(key: str) -> Path:
    filename, url, expected_sha = _MODELS[key]
    try:
        return ensure_model_file(MODEL_DIR / filename, url, expected_sha, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    except ModelDownloadError as exc:
        raise FaceEngineUnavailable(
            "Face verification models couldn't be downloaded or failed their integrity check. "
            "Check the connection and try again."
        ) from exc


def _load():
    global _detector, _recognizer, _last_failure_at
    if _detector is not None:
        return _detector, _recognizer

    with _load_lock:
        if _detector is None:
            if time.monotonic() - _last_failure_at < RETRY_AFTER_FAILURE_SECONDS:
                raise FaceEngineUnavailable("Face verification is temporarily unavailable.")
            try:
                detector_path = _ensure_model("detector")
                recognizer_path = _ensure_model("recognizer")
                detector = cv2.FaceDetectorYN.create(
                    str(detector_path), "", (320, 320), settings.identity_detection_score, 0.3, 5000
                )
                recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
            except FaceEngineUnavailable:
                _last_failure_at = time.monotonic()
                raise
            except cv2.error as exc:
                _last_failure_at = time.monotonic()
                raise FaceEngineUnavailable("Face verification models couldn't be loaded.") from exc
            _detector, _recognizer = detector, recognizer
            logger.info("Face verification models ready")
    return _detector, _recognizer


def is_available() -> bool:
    try:
        _load()
    except FaceEngineUnavailable:
        return False
    return True


async def warm_up() -> None:
    """Fetch and load the models at startup so the first candidate doesn't wait."""
    try:
        await asyncio.to_thread(_load)
    except FaceEngineUnavailable:
        logger.warning("Face verification models unavailable at startup; will retry on first use")


# --- Core analysis ---------------------------------------------------------


def decode_image(data: bytes) -> np.ndarray | None:
    """BGR array from encoded image bytes, or None if it isn't a usable image."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                return None
            return _pil_to_bgr(image)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    # Phone photos store their rotation in EXIF; a sideways face isn't detected.
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, (255, 255, 255))
        image.paste(rgba, mask=rgba.split()[-1])
    else:
        image = image.convert("RGB")
    image.thumbnail((MAX_ANALYSIS_SIDE, MAX_ANALYSIS_SIDE))
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _frame_is_dark(image: np.ndarray) -> bool:
    return float(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).mean()) < settings.identity_min_brightness


def analyse(image: np.ndarray, *, min_face_px: int, scale: float = 1.0) -> FaceAnalysis:
    """Detect faces in a BGR image and embed the face if exactly one usable face is present.

    `scale` is how much `image` was enlarged from its source, so the face-size
    check is made against the pixels that actually existed.
    """
    detector, recognizer = _load()
    height, width = image.shape[:2]

    with _infer_lock:
        detector.setInputSize((width, height))
        _, detections = detector.detect(image)
        # Row layout: x, y, w, h, five landmark (x, y) pairs, score.
        faces = [] if detections is None else sorted(detections, key=lambda f: f[2] * f[3], reverse=True)

        if not faces:
            return FaceAnalysis(FrameOutcome.no_face, hint="too_dark" if _frame_is_dark(image) else None)

        main = faces[0]
        others = [f for f in faces[1:] if f[2] >= main[2] * settings.identity_secondary_face_ratio]
        if others:
            return FaceAnalysis(FrameOutcome.multiple_faces)

        face_px = float(main[2]) / scale
        if face_px < min_face_px:
            return FaceAnalysis(FrameOutcome.low_quality, hint="too_small", face_px=face_px)

        aligned = recognizer.alignCrop(image, main)
        gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        if float(gray.mean()) < settings.identity_min_brightness:
            return FaceAnalysis(FrameOutcome.low_quality, hint="too_dark", face_px=face_px)
        if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < settings.identity_min_sharpness:
            return FaceAnalysis(FrameOutcome.low_quality, hint="blurry", face_px=face_px)

        feature = recognizer.feature(aligned).flatten().astype(np.float32)

    norm = float(np.linalg.norm(feature))
    if not np.isfinite(norm) or norm == 0.0:
        return FaceAnalysis(FrameOutcome.low_quality, hint="blurry", face_px=face_px)
    return FaceAnalysis(FrameOutcome.ok, face_px=face_px, embedding=feature / norm)


def analyse_frame_bytes(data: bytes) -> FaceAnalysis:
    """One webcam frame, as sent by the browser."""
    image = decode_image(data)
    if image is None:
        return FaceAnalysis(FrameOutcome.no_face, hint="unreadable_frame")
    return analyse(image, min_face_px=settings.identity_min_face_px_live)


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two unit-length embeddings."""
    return float(np.dot(a, b))


def mean_embedding(embeddings: list[np.ndarray]) -> np.ndarray:
    mean = np.mean(np.stack(embeddings), axis=0)
    return (mean / np.linalg.norm(mean)).astype(np.float32)


# --- Resume photos ---------------------------------------------------------

# When no usable face is found, the most informative reason wins.
_UNUSABLE_PRIORITY = ("multiple_faces", "too_small", "too_dark", "blurry")


def extract_resume_photo(filename: str, content: bytes) -> ResumePhoto:
    """Find a usable profile photo in a resume and embed it.

    Raises FaceEngineUnavailable only if the resume has images to analyse and
    the models can't run - a resume without images needs no models at all.
    """
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "pdf":
        images = _pdf_images(content)
    elif suffix == "docx":
        images = _docx_images(content)
    else:
        return ResumePhoto(PhotoStatus.not_found, "no_images")

    candidates = [img for img in images if _plausible_photo(img)]
    if not candidates:
        return ResumePhoto(PhotoStatus.not_found, "no_images")

    best: FaceAnalysis | None = None
    problems: Counter[str] = Counter()
    dark_without_face = False
    for image in candidates:
        short_side = min(image.shape[:2])
        scale = DETECTION_MIN_SIDE / short_side if short_side < DETECTION_MIN_SIDE else 1.0
        work = (
            cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            if scale > 1.0
            else image
        )
        result = analyse(work, min_face_px=settings.identity_min_face_px_resume, scale=scale)

        if result.outcome is FrameOutcome.ok:
            if best is None or result.face_px > best.face_px:
                best = result
        elif result.outcome is FrameOutcome.multiple_faces:
            problems["multiple_faces"] += 1
        elif result.outcome is FrameOutcome.low_quality and result.hint:
            problems[result.hint] += 1
        elif result.hint == "too_dark":
            dark_without_face = True

    if best is not None:
        return ResumePhoto(PhotoStatus.usable, embedding=best.embedding)

    for reason in _UNUSABLE_PRIORITY:
        if problems[reason]:
            return ResumePhoto(PhotoStatus.unusable, reason)
    # No face was ever seen, so this stays "not found" - a dark logo shouldn't
    # be reported as a bad photo - but a dark image is worth mentioning.
    return ResumePhoto(PhotoStatus.not_found, "too_dark" if dark_without_face else "no_face")


def _plausible_photo(image: np.ndarray) -> bool:
    height, width = image.shape[:2]
    short_side, long_side = min(height, width), max(height, width)
    return short_side >= MIN_RESUME_IMAGE_SIDE and long_side / short_side <= MAX_RESUME_IMAGE_ASPECT


def _pdf_images(content: bytes) -> list[np.ndarray]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        pages = list(reader.pages[:MAX_RESUME_PDF_PAGES])
    except Exception:
        return []

    images: list[np.ndarray] = []
    for page in pages:
        try:
            embedded = page.images
            count = len(embedded)
        except Exception:
            continue
        for index in range(count):
            if len(images) >= MAX_RESUME_IMAGES:
                return images
            # One undecodable image (JBIG2, odd colour spaces) mustn't hide the rest.
            try:
                pil = embedded[index].image
                if pil is None or pil.width * pil.height > MAX_IMAGE_PIXELS:
                    continue
                images.append(_pil_to_bgr(pil))
            except Exception:
                continue
    return images


def _docx_images(content: bytes) -> list[np.ndarray]:
    images: list[np.ndarray] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if len(images) >= MAX_RESUME_IMAGES:
                    break
                if not info.filename.startswith("word/media/"):
                    continue
                if Path(info.filename).suffix.lower() not in DOCX_IMAGE_SUFFIXES:
                    continue
                if info.file_size > MAX_DOCX_MEDIA_BYTES:
                    continue
                image = decode_image(archive.read(info))
                if image is not None:
                    images.append(image)
    except (zipfile.BadZipFile, OSError):
        return []
    return images
