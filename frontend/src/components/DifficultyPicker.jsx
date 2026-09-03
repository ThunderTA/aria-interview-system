import { DIFFICULTY_LEVELS } from "../constants/difficulty";
import "./DifficultyPicker.css";

/**
 * Starting-difficulty picker for Setup. `value` is a level id (1-5) or null
 * for "Auto" — after the first question, difficulty is always the RL
 * policy's call regardless of what's picked here, so this only sets where
 * the session begins.
 */
export default function DifficultyPicker({ value, onChange }) {
  return (
    <div className="difficulty-picker" role="radiogroup" aria-label="Starting difficulty">
      <button
        type="button"
        role="radio"
        aria-checked={value === null}
        className={`difficulty-pill${value === null ? " difficulty-pill--selected" : ""}`}
        onClick={() => onChange(null)}
      >
        Auto
        <span className="difficulty-pill__hint">from resume</span>
      </button>

      {DIFFICULTY_LEVELS.map((level) => (
        <button
          key={level.id}
          type="button"
          role="radio"
          aria-checked={value === level.id}
          className={`difficulty-pill${value === level.id ? " difficulty-pill--selected" : ""}`}
          onClick={() => onChange(level.id)}
        >
          {level.label}
        </button>
      ))}
    </div>
  );
}
