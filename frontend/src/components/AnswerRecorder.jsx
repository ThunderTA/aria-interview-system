import { useState } from "react";
import useAudioRecorder from "../hooks/useAudioRecorder";
import "./AnswerRecorder.css";

const BAR_COUNT = 32;

function formatTime(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const s = String(totalSeconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

/**
 * Speak-or-type answer input.
 *
 * Typing stays available rather than being a hidden fallback: microphones get
 * blocked, and an interview the candidate cannot answer at all is worse than
 * one answered by keyboard.
 */
export default function AnswerRecorder({
  onSubmitAudio,
  onSubmitText,
  onStart,
  onDiscard,
  disabled,
}) {
  const recorder = useAudioRecorder();
  const [mode, setMode] = useState("speak");
  const [text, setText] = useState("");

  const handleStart = async () => {
    const started = await recorder.start();
    // Only begin sampling camera frames once the mic is actually live, so the
    // frames line up with the audio being scored.
    if (started) onStart?.();
  };

  const handleStop = async () => {
    const result = await recorder.stop();
    if (result?.blob?.size) {
      onSubmitAudio(result.blob, result.extension);
    } else {
      onDiscard?.();
    }
  };

  const handleCancel = () => {
    recorder.cancel();
    onDiscard?.();
  };

  if (mode === "type") {
    return (
      <div className="answer-box">
        <div className="answer-box__head">
          <label className="interview-panel__label" htmlFor="answer">
            Your answer
          </label>
          <button type="button" className="mode-switch" onClick={() => setMode("speak")}>
            Speak instead
          </button>
        </div>
        <textarea
          id="answer"
          className="answer-input"
          rows={7}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Answer as you would out loud — a few sentences is enough."
          disabled={disabled}
        />
        <div className="answer-box__foot">
          <span className="answer-box__count">
            {text.trim() ? `${text.trim().split(/\s+/).length} words` : " "}
          </span>
          <button
            type="button"
            className="interview-submit"
            onClick={() => onSubmitText(text.trim())}
            disabled={!text.trim() || disabled}
          >
            Submit answer
          </button>
        </div>
        <p className="answer-box__hint">
          Typed answers are scored on content only — pace, pauses and filler words need audio.
        </p>
      </div>
    );
  }

  return (
    <div className="recorder">
      {recorder.recording ? (
        <>
          <div className="recorder__live">
            <span className="recorder__dot" aria-hidden="true" />
            <span className="recorder__time">{formatTime(recorder.seconds)}</span>
            <span className="recorder__status">Listening…</span>
          </div>

          <div className="recorder__wave" ref={recorder.levelTargetRef} aria-hidden="true">
            {Array.from({ length: BAR_COUNT }).map((_, i) => {
              // Centre bars react most, so the shape reads as a voice, not a bar
              // chart. The falloff is fixed per bar; only --level changes, and
              // the hook writes that straight to the DOM each frame.
              const falloff = 1 - Math.abs(i - BAR_COUNT / 2) / (BAR_COUNT / 2);
              return <span key={i} style={{ "--falloff": falloff.toFixed(3) }} />;
            })}
          </div>

          <div className="recorder__actions">
            <button type="button" className="recorder__stop" onClick={handleStop}>
              Done answering
            </button>
            <button type="button" className="recorder__cancel" onClick={handleCancel}>
              Discard
            </button>
          </div>
        </>
      ) : (
        <>
          <button
            type="button"
            className="recorder__start"
            onClick={handleStart}
            disabled={disabled || !recorder.supported}
          >
            <span className="recorder__mic" aria-hidden="true" />
            Start answering
          </button>
          <p className="recorder__hint">
            Speak your answer out loud. ARIA scores what you say and how you say it — everything
            is transcribed on this machine.
          </p>
          {recorder.error && <p className="recorder__error">{recorder.error}</p>}
          <button type="button" className="mode-switch" onClick={() => setMode("type")}>
            Type it instead
          </button>
        </>
      )}
    </div>
  );
}
