import { useCallback, useEffect, useRef, useState } from "react";

// Frames are sampled, not streamed: gaze and posture don't change meaningfully
// between consecutive frames, and one per second keeps the upload small.
const SAMPLE_INTERVAL_MS = 1000;
// MediaPipe's face landmarker works comfortably at this width, and it keeps
// each JPEG to a few KB.
const FRAME_WIDTH = 320;
const JPEG_QUALITY = 0.7;
// Identity embeddings need more facial detail than gaze does.
const STILL_WIDTH = 640;
const STILL_QUALITY = 0.85;

function errorCodeFor(err) {
  switch (err?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "denied";
    case "NotFoundError":
    case "OverconstrainedError":
      return "not_found";
    case "NotReadableError":
    case "AbortError":
      return "in_use";
    default:
      return "unknown";
  }
}

const OPTIONAL_MESSAGES = {
  denied: "Camera access was blocked. The interview still works - only the visual scores will be missing.",
  not_found: "No camera was found. The interview still works without it.",
  in_use: "The camera is being used by another app. Close it and try again.",
  unknown: "The camera couldn't be started.",
  unsupported: "This browser can't access a camera.",
  stopped: "The camera stopped.",
};

/**
 * Webcam preview plus frame capture for visual analysis and identity checks.
 *
 * `errorCode` lets a caller that *requires* the camera show its own guidance,
 * while `error` keeps the optional-camera wording used elsewhere.
 */
export default function useCamera() {
  const [enabled, setEnabled] = useState(false);
  const [errorCode, setErrorCode] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);
  const stillCanvasRef = useRef(null);
  const framesRef = useRef([]);
  const samplerRef = useRef(null);

  const stop = useCallback(() => {
    clearInterval(samplerRef.current);
    samplerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => {
      t.onended = null;
      t.stop();
    });
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setEnabled(false);
  }, []);

  useEffect(() => stop, [stop]);

  /** Callback ref: the stream follows whichever <video> is currently mounted. */
  const attachVideo = useCallback((element) => {
    videoRef.current = element;
    if (element && streamRef.current && element.srcObject !== streamRef.current) {
      element.srcObject = streamRef.current;
      element.play().catch(() => {});
    }
  }, []);

  const start = useCallback(async () => {
    setErrorCode(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorCode("unsupported");
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      });
      streamRef.current = stream;
      // Permission revoked or the device unplugged mid-interview.
      stream.getVideoTracks().forEach((track) => {
        track.onended = () => {
          stop();
          setErrorCode("stopped");
        };
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      setEnabled(true);
      return true;
    } catch (err) {
      setErrorCode(errorCodeFor(err));
      return false;
    }
  }, [stop]);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;

    const canvas = (canvasRef.current ??= document.createElement("canvas"));
    const scale = FRAME_WIDTH / video.videoWidth;
    canvas.width = FRAME_WIDTH;
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => {
        if (blob) framesRef.current.push(blob);
      },
      "image/jpeg",
      JPEG_QUALITY
    );
  }, []);

  /** One higher-resolution JPEG of the current frame, or null if there's no picture yet. */
  const captureStill = useCallback(() => {
    const video = videoRef.current;
    if (!streamRef.current || !video || !video.videoWidth) return Promise.resolve(null);

    // Own canvas, so a check never collides with answer sampling.
    const canvas = (stillCanvasRef.current ??= document.createElement("canvas"));
    const scale = Math.min(1, STILL_WIDTH / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", STILL_QUALITY));
  }, []);

  /** Begin collecting frames for one answer. */
  const startSampling = useCallback(() => {
    framesRef.current = [];
    if (!streamRef.current) return;
    captureFrame();
    samplerRef.current = setInterval(captureFrame, SAMPLE_INTERVAL_MS);
  }, [captureFrame]);

  /** Stop collecting and hand back the frames gathered. */
  const stopSampling = useCallback(() => {
    clearInterval(samplerRef.current);
    samplerRef.current = null;
    const frames = framesRef.current;
    framesRef.current = [];
    return frames;
  }, []);

  return {
    enabled,
    errorCode,
    error: errorCode ? OPTIONAL_MESSAGES[errorCode] : null,
    attachVideo,
    start,
    stop,
    captureStill,
    startSampling,
    stopSampling,
  };
}
