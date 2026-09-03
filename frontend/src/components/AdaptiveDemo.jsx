import { useState } from "react";
import "./AdaptiveDemo.css";

const SCENARIOS = {
  strong: {
    label: "Answering well",
    difficulty: "Level 4 · Challenging",
    question:
      "How would you design a rate limiter for a public API that needs to hold up under millions of requests a second?",
    note: "Recent scores were high, so the policy raised the difficulty.",
  },
  struggling: {
    label: "Finding it hard",
    difficulty: "Level 2 · Easier",
    question: "What's the difference between an array and a linked list?",
    note: "Recent scores were low, so the policy stepped the difficulty back down.",
  },
};

export default function AdaptiveDemo() {
  const [scenario, setScenario] = useState("strong");
  const current = SCENARIOS[scenario];

  return (
    <div className="adaptive-demo">
      <div className="adaptive-demo__toggle" role="tablist" aria-label="Interview scenario">
        {Object.entries(SCENARIOS).map(([key, s]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={scenario === key}
            className={`adaptive-demo__toggle-btn${scenario === key ? " is-active" : ""}`}
            onClick={() => setScenario(key)}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="adaptive-demo__card" key={scenario}>
        <span className="adaptive-demo__badge">{current.difficulty}</span>
        <p className="adaptive-demo__question">{current.question}</p>
        <p className="adaptive-demo__note">{current.note}</p>
      </div>
    </div>
  );
}
