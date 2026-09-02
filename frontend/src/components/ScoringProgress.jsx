import { useEffect, useState } from "react";
import "./ScoringProgress.css";

// Mirrors what the server actually does during POST /answer: the LLM grades the
// answer against the rubric, then generates the next question. The timings are
// approximate — the stages advance on a timer, then the last one holds until the
// response lands, so a slow model never makes the UI claim it has finished.
const STAGES = [
  { label: "Reading your answer", after: 0 },
  { label: "Scoring against the rubric", after: 2500 },
  { label: "Choosing the next question", after: 20000 },
];

export default function ScoringProgress() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Date.now() - started), 500);
    return () => clearInterval(id);
  }, []);

  const activeIndex = STAGES.reduce((acc, stage, i) => (elapsed >= stage.after ? i : acc), 0);

  return (
    <div className="scoring" role="status" aria-live="polite">
      <div className="scoring__head">
        <span className="scoring__spinner" aria-hidden="true" />
        <p className="scoring__title">{STAGES[activeIndex].label}…</p>
        <span className="scoring__elapsed">{Math.floor(elapsed / 1000)}s</span>
      </div>

      <ol className="scoring__stages">
        {STAGES.map((stage, i) => (
          <li
            key={stage.label}
            className={`scoring__stage${i < activeIndex ? " scoring__stage--done" : ""}${
              i === activeIndex ? " scoring__stage--active" : ""
            }`}
          >
            {stage.label}
          </li>
        ))}
      </ol>

      <p className="scoring__hint">
        Scoring runs on a local model, so this takes around half a minute — no data leaves your
        machine.
      </p>
    </div>
  );
}
