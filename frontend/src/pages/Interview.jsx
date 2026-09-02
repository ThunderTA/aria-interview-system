import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import { getRole } from "../constants/roles";
import "./Interview.css";

const SAMPLE_QUESTIONS = {
  SDE: "Walk me through how you'd design a URL shortener that handles a few million redirects a day.",
  HR: "Tell me about a time a project you were leading fell behind schedule. What did you do?",
};

export default function Interview() {
  const navigate = useNavigate();
  const location = useLocation();
  const role = getRole(location.state?.role);
  const [micActive, setMicActive] = useState(false);

  return (
    <div className="interview-shell">
      <AppHeader backTo="/setup" backLabel="Setup" />

      <Notice variant="preview" title="Preview mode.">
        This is the interview screen's layout. Speech capture, transcription, adaptive
        questioning, and visual analysis are wired up in later milestones — nothing here is
        recording or scoring you yet.
      </Notice>

      <div className="interview-grid">
        <section className="interview-main">
          <div className="interview-meta">
            <span className="interview-chip interview-chip--role">{role.short}</span>
            <span className="interview-chip">Question 1 of 8</span>
            <span className="interview-chip interview-chip--difficulty">Difficulty · Medium</span>
          </div>

          <h1 className="interview-question">{SAMPLE_QUESTIONS[role.id]}</h1>
          <p className="interview-sample-label">Sample question · not generated live</p>

          <div className="interview-controls">
            <button
              type="button"
              className={`mic-button${micActive ? " mic-button--active" : ""}`}
              onClick={() => setMicActive((v) => !v)}
              aria-pressed={micActive}
            >
              <span className="mic-button__dot" />
              {micActive ? "Stop answering" : "Start answering"}
            </button>
            <button
              type="button"
              className="interview-finish"
              onClick={() => navigate("/report", { state: { role: role.id } })}
            >
              Finish preview →
            </button>
          </div>

          <div className="interview-transcript">
            <p className="interview-panel__label">Live transcript</p>
            {micActive ? (
              <div className="interview-listening">
                <div className="interview-wave" aria-hidden="true">
                  {Array.from({ length: 14 }).map((_, i) => (
                    <span key={i} style={{ animationDelay: `${(i % 7) * 90}ms` }} />
                  ))}
                </div>
                <p>Transcription appears here once Whisper is connected.</p>
              </div>
            ) : (
              <p className="interview-placeholder">
                Your answer will be transcribed here in real time.
              </p>
            )}
          </div>
        </section>

        <aside className="interview-side">
          <div className="interview-panel">
            <p className="interview-panel__label">Camera</p>
            <div className="camera-frame">
              <span className="camera-frame__text">Camera preview</span>
            </div>
            <p className="interview-panel__hint">
              Eye contact, expression, and posture analysis land with the CV milestone.
            </p>
          </div>

          <div className="interview-panel">
            <p className="interview-panel__label">Live signals</p>
            <ul className="signal-list">
              <li>
                <span>Speaking pace</span>
                <span className="signal-list__value">—</span>
              </li>
              <li>
                <span>Filler words</span>
                <span className="signal-list__value">—</span>
              </li>
              <li>
                <span>Eye contact</span>
                <span className="signal-list__value">—</span>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
