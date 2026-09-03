import { useCallback, useEffect, useRef, useState } from "react";

// Frames are sampled, not streamed: gaze and posture don't change meaningfully
// between consecutive frames, and one per second keeps the upload small.
const SAMPLE_INTERVAL_MS = 1000;
// MediaPipe's face landmarker works comfortably at this width, and it keeps
// each JPEG to a few KB.
const FRAME_WIDTH = 320;
const JPEG_QUALITY = 0.7;

/**
 * Webcam preview plus periodic frame capture for visual analysis.
 *
 * The camera is optional throughout: if it is denied or unavailable the
 * interview carries on and the visual scores are simply absent, rather than
 * the answer failing.
 */
export default function useCamera() {
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);
  const framesRef = useRef([]);
  const samplerRef = useRef(null);

  const stop = useCallback(() => {
    clearInterval(samplerRef.current);
    samplerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setEnabled(false);
  }, []);

  useEffect(() => stop, [stop]);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("This browser can't access a camera.");
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      setEnabled(true);
      return true;
    } catch (err) {
      setError(
        err.name === "NotAllowedError"
          ? "Camera access was blocked. The interview still works — only the visual scores will be missing."
          : "No camera was found. The interview still works without it."
      );
      return false;
    }
  }, []);

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

  return { enabled, error, videoRef, start, stop, startSampling, stopSampling };
}
