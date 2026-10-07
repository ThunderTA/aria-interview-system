import { useCallback, useEffect, useRef, useState } from "react";
import { synthesizeSpeech } from "../api/speech";

// A beat between sentences: synthesised clips are trimmed of silence, and
// played back to back they sound rushed.
const SENTENCE_GAP_MS = 140;

/** Sentence-sized pieces, so the first can play while the rest are synthesised. */
export function splitForSpeech(text) {
  // Split only where a sentence plausibly ends, so "Node.js" or "e.g. this" stay whole.
  return text
    .split(/(?<=[.!?])\s+(?=["'A-Z0-9])/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function pickBrowserVoice() {
  const english = (window.speechSynthesis?.getVoices() ?? []).filter((v) => /^en[-_]/i.test(v.lang));
  return (
    english.find((v) => /natural|neural|premium|enhanced|samantha|google us|aria|jenny/i.test(v.name)) ??
    english[0] ??
    null
  );
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function playBlob(blob, audioRef, isCurrent) {
  return new Promise((resolve, reject) => {
    if (!isCurrent()) {
      resolve();
      return;
    }
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audioRef.current = audio;
    const finished = () => {
      URL.revokeObjectURL(url);
      resolve();
    };
    audio.onended = finished;
    // cancel() pauses the element; treat that as finished rather than hanging.
    audio.onpause = () => {
      if (!isCurrent()) finished();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Playback failed"));
    };
    audio.play().catch((err) => {
      URL.revokeObjectURL(url);
      reject(err);
    });
  });
}

function speakWithBrowser(text, isCurrent) {
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    if (!synth || !text || !isCurrent()) {
      resolve();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    const voice = pickBrowserVoice();
    if (voice) utterance.voice = voice;
    utterance.onend = resolve;
    utterance.onerror = resolve;
    synth.speak(utterance);
  });
}

/**
 * The interviewer's voice.
 *
 * Uses the local Kokoro voice from the backend, sentence by sentence; if that
 * fails, it switches to the browser's built-in speech for the rest of the
 * interview rather than going silent.
 */
export default function useInterviewerVoice() {
  const [speaking, setSpeaking] = useState(false);
  const [engine, setEngine] = useState("local");

  const tokenRef = useRef(0);
  const audioRef = useRef(null);
  const controllerRef = useRef(null);
  const browserOnlyRef = useRef(false);

  const cancel = useCallback(() => {
    tokenRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
    audioRef.current?.pause();
    audioRef.current = null;
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, []);

  useEffect(() => cancel, [cancel]);

  /** Speak `text`. Resolves once it has been spoken, or cancelled. */
  const speak = useCallback(
    async (text) => {
      cancel();
      const token = tokenRef.current;
      const isCurrent = () => token === tokenRef.current;
      setSpeaking(true);

      try {
        const sentences = splitForSpeech(text);
        let spoken = 0;

        if (!browserOnlyRef.current) {
          const controller = new AbortController();
          controllerRef.current = controller;
          // All requested at once: synthesis outpaces playback, so each clip is
          // ready by the time the one before it ends.
          const requests = sentences.map((sentence) =>
            synthesizeSpeech(sentence, { signal: controller.signal })
          );
          requests.forEach((request) => request.catch(() => {}));

          try {
            for (const request of requests) {
              const blob = await request;
              if (!isCurrent()) return;
              if (spoken > 0) await wait(SENTENCE_GAP_MS);
              await playBlob(blob, audioRef, isCurrent);
              spoken += 1;
            }
            return;
          } catch (err) {
            if (!isCurrent()) return;
            // Autoplay was blocked: the caption is still on screen, and the
            // local voice itself is fine, so don't abandon it.
            if (err?.name === "NotAllowedError") return;
            browserOnlyRef.current = true;
            setEngine("browser");
          }
        }

        await speakWithBrowser(sentences.slice(spoken).join(" "), isCurrent);
      } finally {
        if (isCurrent()) setSpeaking(false);
      }
    },
    [cancel]
  );

  return { speak, cancel, speaking, engine };
}
