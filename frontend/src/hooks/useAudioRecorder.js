import { useCallback, useEffect, useRef, useState } from "react";

/** Codecs browsers actually produce, in the order we'd prefer them. */
const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return null;
  return PREFERRED_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

function extensionFor(mimeType) {
  if (!mimeType) return "webm";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}

/**
 * Microphone recording with a live input level for the waveform.
 *
 * Owns the MediaStream so the browser's recording indicator clears the moment
 * a recording stops, rather than lingering for the whole interview.
 */
export default function useAudioRecorder() {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);

  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const rafRef = useRef(null);
  const timerRef = useRef(null);
  // The waveform container. Input level is written straight onto it as a CSS
  // variable: at 60fps, putting it in React state would re-render the whole
  // interview screen on every frame for a purely decorative effect.
  const levelTargetRef = useRef(null);

  const setLevel = useCallback((value) => {
    levelTargetRef.current?.style.setProperty("--level", value.toFixed(3));
  }, []);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    audioContextRef.current?.close().catch(() => {});
    audioContextRef.current = null;
    setLevel(0);
  }, [setLevel]);

  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || !pickMimeType()) {
      setError("This browser can't record audio. You can type your answer instead.");
      return false;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      setError(
        err.name === "NotAllowedError"
          ? "Microphone access was blocked. Allow it in your browser, or type your answer instead."
          : "No microphone was found. You can type your answer instead."
      );
      return false;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, { mimeType });
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start(250);
    recorderRef.current = recorder;

    // Live level, purely for the waveform.
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const buffer = new Uint8Array(analyser.frequencyBinCount);

    const sample = () => {
      analyser.getByteTimeDomainData(buffer);
      // RMS around the 128 midpoint, scaled to roughly 0..1.
      let sum = 0;
      for (const v of buffer) sum += (v - 128) ** 2;
      setLevel(Math.min(1, Math.sqrt(sum / buffer.length) / 40));
      rafRef.current = requestAnimationFrame(sample);
    };
    sample();

    setSeconds(0);
    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    setRecording(true);
    return true;
  }, []);

  /** Stops recording and resolves with the finished audio. */
  const stop = useCallback(
    () =>
      new Promise((resolve) => {
        const recorder = recorderRef.current;
        if (!recorder || recorder.state === "inactive") {
          resolve(null);
          return;
        }
        recorder.onstop = () => {
          const mimeType = recorder.mimeType;
          const blob = new Blob(chunksRef.current, { type: mimeType });
          cleanup();
          setRecording(false);
          resolve({ blob, extension: extensionFor(mimeType), seconds });
        };
        recorder.stop();
      }),
    [cleanup, seconds]
  );

  const cancel = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      recorder.stop();
    }
    cleanup();
    setRecording(false);
    setSeconds(0);
  }, [cleanup]);

  return {
    recording,
    seconds,
    error,
    start,
    stop,
    cancel,
    levelTargetRef,
    supported: !!pickMimeType(),
  };
}
