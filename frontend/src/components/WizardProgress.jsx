import "./WizardProgress.css";

/**
 * Step indicator for a multi-step wizard. `steps` is an array of labels;
 * `current` is the active step's index (0-based). Steps before `current`
 * are shown completed (checkmark), steps after are upcoming (muted).
 */
export default function WizardProgress({ steps, current }) {
  return (
    <ol className="wizard-progress" aria-label="Setup steps">
      {steps.map((label, i) => {
        const status = i < current ? "done" : i === current ? "active" : "upcoming";
        return (
          <li key={label} className={`wizard-progress__step wizard-progress__step--${status}`}>
            <span className="wizard-progress__marker" aria-hidden="true">
              {status === "done" ? (
                <svg viewBox="0 0 16 16" width="12" height="12" fill="none">
                  <path
                    d="M3.5 8.5l3 3 6-6.5"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                i + 1
              )}
            </span>
            <span className="wizard-progress__label">{label}</span>
            {i < steps.length - 1 && <span className="wizard-progress__line" aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}
