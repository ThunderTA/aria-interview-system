import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import Notice from "../components/Notice";
import { getReport } from "../api/sessions";
import { getRole } from "../constants/roles";
import "./Report.css";

const RUBRIC_LABELS = {
  correctness: "Correctness",
  depth: "Depth",
  relevance: "Relevance",
  clarity: "Clarity",
};

export default function Report() {
  const location = useLocation();
  const sessionId = location.state?.sessionId;

  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sessionId) {
      setError("No session selected. Start an interview from your dashboard.");
      return;
    }
    getReport(sessionId)
      .then(setReport)
      .catch((err) => setError(err.response?.data?.detail || "Could not load this report."));
  }, [sessionId]);

  if (error) {
    return (
      <div className="report-shell">
        <AppHeader backTo="/dashboard" backLabel="Dashboard" />
        <Notice title="Report unavailable.">{error}</Notice>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="report-shell">
        <AppHeader backTo="/dashboard" backLabel="Dashboard" />
        <p className="report-empty">Loading your report…</p>
      </div>
    );
  }

  const { session, strengths, improvements } = report;
  const role = getRole(session.role);
  const answered = session.questions.filter((q) => q.content_score != null);

  const tiles = [
    { label: "Overall", value: session.overall_score, hint: "Across all measured dimensions" },
    { label: "Content", value: session.content_score_avg, hint: "Correctness, depth, relevance, clarity" },
    { label: "Delivery", value: session.delivery_score_avg, hint: "Pace, pauses, filler words" },
    { label: "Visual", value: session.visual_score_avg, hint: "Eye contact, expression, posture" },
  ];

  return (
    <div className="report-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <div className="report-intro">
        <h1>Session report</h1>
        <p>
          {role.label} · {answered.length} question{answered.length === 1 ? "" : "s"} answered ·{" "}
          {new Date(session.started_at).toLocaleDateString()}
        </p>
      </div>

      <div className="score-grid">
        {tiles.map((tile) => (
          <section key={tile.label} className="score-tile">
            <p className="score-tile__label">{tile.label}</p>
            <p className={`score-tile__value${tile.value == null ? " score-tile__value--muted" : ""}`}>
              {tile.value == null ? "—" : Math.round(tile.value)}
            </p>
            <p className="score-tile__hint">{tile.hint}</p>
          </section>
        ))}
      </div>

      {session.delivery_score_avg == null && (
        <Notice title="Content only, for now.">
          Delivery and visual scores stay empty until the speech and camera analysis milestones
          land. The overall score reflects content alone rather than guessing at the rest.
        </Notice>
      )}

      <div className="report-columns">
        <section className="report-panel">
          <h2>Strengths</h2>
          {strengths.length ? (
            <ul className="report-list report-list--strength">
              {strengths.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="report-empty">No strengths were identified in this session.</p>
          )}
        </section>

        <section className="report-panel">
          <h2>Areas to improve</h2>
          {improvements.length ? (
            <ul className="report-list report-list--improve">
              {improvements.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="report-empty">Nothing flagged for improvement.</p>
          )}
        </section>
      </div>

      <section className="report-panel">
        <h2>Question breakdown</h2>
        {answered.length === 0 ? (
          <p className="report-empty">No questions were answered in this session.</p>
        ) : (
          <ol className="breakdown">
            {answered.map((q) => (
              <li key={q.question_id} className="breakdown__item">
                <div className="breakdown__head">
                  <span className="breakdown__score">{Math.round(q.content_score)}</span>
                  <div>
                    <p className="breakdown__question">{q.text}</p>
                    <p className="breakdown__meta">
                      {q.topic} · difficulty {q.difficulty_level}
                    </p>
                  </div>
                </div>

                {q.rubric && (
                  <div className="rubric">
                    {Object.entries(RUBRIC_LABELS).map(([key, label]) => (
                      <div key={key} className="rubric__row">
                        <span className="rubric__label">{label}</span>
                        <span className="rubric__bar">
                          <span
                            className="rubric__fill"
                            style={{ width: `${(q.rubric[key] ?? 0) * 10}%` }}
                          />
                        </span>
                        <span className="rubric__value">{q.rubric[key] ?? 0}/10</span>
                      </div>
                    ))}
                  </div>
                )}

                {q.feedback_text && <p className="breakdown__feedback">{q.feedback_text}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="report-actions">
        <Link to="/setup" className="report-cta">
          Practise again →
        </Link>
      </div>
    </div>
  );
}
