import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Logo from "./Logo";
import { frequencyForIndex, playTone } from "../utils/tones";
import "./BrandPanel.css";

const FEATURES = [
  "Adaptive question difficulty",
  "Real-time speech & visual feedback",
  "Progress tracked across sessions",
];

const BAR_COUNT = 24;
const HIT_DURATION_MS = 400;

export default function BrandPanel() {
  // Bars currently mid-pluck, so the click animation can layer on top of the
  // ambient idle motion without the two fighting over the same CSS property.
  const [hitBars, setHitBars] = useState(() => new Set());
  const timeoutsRef = useRef({});

  const touchBar = useCallback((index) => {
    playTone(frequencyForIndex(index));

    setHitBars((prev) => new Set(prev).add(index));
    clearTimeout(timeoutsRef.current[index]);
    timeoutsRef.current[index] = setTimeout(() => {
      setHitBars((prev) => {
        const next = new Set(prev);
        next.delete(index);
        return next;
      });
    }, HIT_DURATION_MS);
  }, []);

  return (
    <aside className="brand-panel">
      <div className="brand-panel__glow" aria-hidden="true" />
      <div className="brand-panel__grid" aria-hidden="true" />

      <div className="brand-panel__content">
        <Link to="/" className="brand-panel__mark">
          <Logo size={28} />
          <span>ARIA</span>
        </Link>

        <h1 className="brand-panel__headline">
          Practice interviews that <span>adapt to you.</span>
        </h1>
        <p className="brand-panel__sub">
          Role-specific mock interviews, scored in real time on what you said and how you said
          it - so you walk into the real one ready.
        </p>

        <ul className="brand-panel__features">
          {FEATURES.map((f) => (
            <li key={f}>
              <span className="brand-panel__dot" />
              {f}
            </li>
          ))}
        </ul>
      </div>

      {/* Decorative, but touchable: each bar plays a note on the pentatonic
          scale, so tapping across them in any order still sounds musical. */}
      <div className="brand-panel__waveform">
        {Array.from({ length: BAR_COUNT }).map((_, i) => (
          <button
            key={i}
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            className={`brand-panel__bar${hitBars.has(i) ? " brand-panel__bar--hit" : ""}`}
            style={{ animationDelay: `${(i % 8) * 90}ms` }}
            onPointerDown={() => touchBar(i)}
          />
        ))}
      </div>
    </aside>
  );
}
