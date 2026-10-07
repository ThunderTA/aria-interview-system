import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import AppHeader from "../components/AppHeader";
import AttentionReport from "../components/AttentionReport";
import { EyeIcon, IconChip, MicIcon, ScoreIcon, TargetIcon } from "../components/FeatureIcons";
import IdentityReport from "../components/IdentityReport";
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

const TILE_ICONS = {
  Overall: { icon: TargetIcon, tint: "accent" },
  Content: { icon: ScoreIcon, tint: "signal" },
  Delivery: { icon: MicIcon, tint: "accent" },
  Visual: { icon: EyeIcon, tint: "signal" },
};

/** One question's back-and-forth in a conversational interview. */
function ExchangeTranscript({ turns }) {
  const followUps = turns.filter((t) => t.kind === "follow_up").length;
  return (
    <details className="breakdown__exchange">
      <summary>
        The conversation
        {followUps > 0 && ` · ${followUps} follow-up${followUps === 1 ? "" : "s"}`}
      </summary>
      <ol className="exchange">
        {turns.map((turn) => (
          <li key={turn.id} className={`exchange__turn exchange__turn--${turn.speaker}`}>
            <span className="exchange__speaker">{turn.speaker === "interviewer" ? "ARIA" : "You"}</span>
            <span className="exchange__text">{turn.text}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

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
  const isConversation = session.mode === "conversation";
  const answered = session.questions
    .filter((q) => q.content_score != null)
    .map((q, i) => ({ ...q, num: i + 1 }));
  const spokenAnswers = answered.filter((q) => q.wpm != null);
  const avgWpm = spokenAnswers.length
    ? Math.round(spokenAnswers.reduce((sum, q) => sum + q.wpm, 0) / spokenAnswers.length)
    : null;
  const threadTurns = (index) =>
    (session.conversation?.turns ?? []).filter(
      (t) => t.question_index === index && t.kind !== "repeat_request"
    );

  const tiles = [
    { label: "Overall", value: session.overall_score, hint: "Across all measured dimensions" },
    { label: "Content", value: session.content_score_avg, hint: "Correctness, depth, relevance, clarity" },
    { label: "Delivery", value: session.delivery_score_avg, hint: "Pace, pauses, filler words" },
    { label: "Visual", value: session.visual_score_avg, hint: "Eye contact, expression, posture" },
  ];

  return (
    <div className="report-shell">
      <AppHeader backTo="/dashboard" backLabel="Dashboard" />

      <div className="report-header">
        <span className="report-header__badge">{role.short}</span>
        <div>
          <h1 className="report-header__title">Session report</h1>
          <p className="report-header__meta">
            {role.label} · {isConversation ? "Conversational interview · " : ""}
            {answered.length} question{answered.length === 1 ? "" : "s"} answered ·{" "}
            {new Date(session.started_at).toLocaleDateString(undefined, {
              weekday: "short",
              month: "short",
              day: "numeric",
            })}
          </p>
        </div>
      </div>

      <div className="report-layout">
        <div className="report-main">
          <div className="score-grid">
            {tiles.map((tile) => {
              const { icon: Icon, tint } = TILE_ICONS[tile.label];
              return (
                <section key={tile.label} className="score-tile">
                  <IconChip tint={tint}>
                    <Icon />
                  </IconChip>
                  <p className="score-tile__label">{tile.label}</p>
                  <p
                    className={`score-tile__value${tile.value == null ? " score-tile__value--muted" : " gradient-text"}`}
                  >
                    {tile.value == null ? "—" : Math.round(tile.value)}
                  </p>
                  <p className="score-tile__hint">{tile.hint}</p>
                </section>
              );
            })}
          </div>

          {(session.delivery_score_avg == null || session.visual_score_avg == null) && (
            <Notice title="Some dimensions weren't measured.">
              {session.delivery_score_avg == null
                ? "Delivery needs a spoken answer — typed ones are scored on content only. "
                : ""}
              {session.visual_score_avg == null
                ? "Visual scores need the camera on while you answer. "
                : ""}
              Unmeasured dimensions are left out of the overall score rather than counted as zero.
            </Notice>
          )}

          {session.identity?.required && <IdentityReport identity={session.identity} />}

          {session.attention?.checks > 0 && <AttentionReport attention={session.attention} />}

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
                          Q{q.num} · {q.topic} · difficulty {q.difficulty_level}
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

                    {(q.delivery_note || q.visual_note) && (
                      <div className="breakdown__signals">
                        {q.delivery_note && (
                          <span>
                            <strong>{Math.round(q.delivery_score)}</strong> delivery ·{" "}
                            {q.delivery_note}
                          </span>
                        )}
                        {q.visual_note && (
                          <span>
                            <strong>{Math.round(q.gaze_score)}</strong> eye contact ·{" "}
                            {q.visual_note}
                          </span>
                        )}
                      </div>
                    )}

                    {q.attention?.note && <p className="breakdown__attention">{q.attention.note}</p>}

                    {q.feedback_text && <p className="breakdown__feedback">{q.feedback_text}</p>}

                    {isConversation && threadTurns(q.order_index).length > 0 && (
                      <ExchangeTranscript turns={threadTurns(q.order_index)} />
                    )}
                  </li>
                ))}
              </ol>
            )}
          </section>

          <div className="report-actions">
            <Link to="/setup" className="report-cta">
              Practise again →
            </Link>
            <Link to="/dashboard" className="report-cta report-cta--ghost">
              Back to dashboard
            </Link>
          </div>
        </div>

        <aside className="report-side">
          <section className="report-panel report-panel--pace">
            <h2>Speaking pace</h2>
            {spokenAnswers.length ? (
              <>
                <p className="pace-average">
                  <span className="pace-average__value gradient-text">{avgWpm}</span>
                  <span className="pace-average__unit">wpm average</span>
                </p>
                <div className="pace-grid">
                  {spokenAnswers.map((q) => (
                    <div key={q.question_id} className="pace-grid__cell">
                      <span className="pace-grid__q">Q{q.num}</span>
                      <span className="pace-grid__value">{Math.round(q.wpm)}</span>
                      <span className="pace-grid__unit">wpm</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="report-empty">
                No spoken answers in this session — pace is measured from audio.
              </p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
