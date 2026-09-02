# TODO: MediaPipe-based visual analysis, sampled at ~2-5 fps from the WS
# video frames (not full frame-rate). Produces gaze/eye-contact,
# expression, and posture sub-scores per docs/architecture.md.


def analyze_frame(frame_bytes: bytes) -> dict:
    raise NotImplementedError
