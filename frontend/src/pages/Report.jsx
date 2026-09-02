import { Link, useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import { getRole } from "../constants/roles";
import "./Report.css";

const SCORE_TILES = [
  { label: "Overall", hint: "Weighted across all three dimensions" },
  { label: "Content", hint: "Correctness, depth, relevance, clarity" },
  { label: "Delivery", hint: "Pace, pauses, filler words" },
  { label: "Visual", hint: "Eye contact, expression, posture" },
];

export default function Report() {
  const location = useLocation();
  const role = getRole(location.state?.role);

  return (
    <div className="report-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <Notice variant="preview" title="Preview mode.">
        This is the report layout. Scores and feedback stay empty until the scoring engines
        (LLM judge, speech analysis, CV analysis) are connected.
      </Notice>

      <div className="report-intro">
        <h1>Session report</h1>
        <p>
          {role.label} · practice session
        </p>
      </div>

      <div className="score-grid">
        {SCORE_TILES.map((tile) => (
          <section key={tile.label} className="score-tile">
            <p className="score-tile__label">{tile.label}</p>
            <p className="score-tile__value">—</p>
            <p className="score-tile__hint">{tile.hint}</p>
          </section>
        ))}
      </div>

      <div className="report-columns">
        <section className="report-panel">
          <h2>Strengths</h2>
          <p className="report-empty">
            Identified strengths will be listed here once answers are scored.
          </p>
        </section>

        <section className="report-panel">
          <h2>Areas to improve</h2>
          <p className="report-empty">
            Skill gaps and targeted recommendations will appear here.
          </p>
        </section>
      </div>

      <section className="report-panel">
        <h2>Question breakdown</h2>
        <p className="report-empty">
          Each question, your transcript, and its per-answer scores will be listed here.
        </p>
      </section>

      <div className="report-actions">
        <Link to="/dashboard" className="report-primary-link">
          Back to dashboard
        </Link>
        <button type="button" className="report-secondary-button" disabled>
          Download PDF
          <span className="report-soon">Coming soon</span>
        </button>
      </div>
    </div>
  );
}
