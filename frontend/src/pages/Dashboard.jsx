import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getCurrentUser } from "../api/auth";
import { listSessions } from "../api/sessions";
import AppHeader from "../components/AppHeader";
import {
  CalendarIcon,
  CheckCircleIcon,
  FlameIcon,
  IconChip,
  TargetIcon,
} from "../components/FeatureIcons";
import Notice from "../components/Notice";
import { getRole } from "../constants/roles";
import "./Dashboard.css";

function initials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function firstName(name) {
  return name?.split(" ")[0] ?? "";
}

/** Consecutive days up to today on which at least one session was completed. */
function practiceStreak(sessions) {
  const days = new Set(
    sessions.map((s) => new Date(s.started_at).toISOString().slice(0, 10))
  );
  let streak = 0;
  const cursor = new Date();
  while (days.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
}

const TODAY = new Date().toLocaleDateString(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
});

export default function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(location.state?.notice ?? null);

  useEffect(() => {
    // Clear the notice out of history state once read, so refreshing the
    // dashboard afterward doesn't bring it back.
    if (location.state?.notice) navigate(location.pathname, { replace: true, state: {} });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch(() => setError("Could not load your profile - please log in again."));
    listSessions()
      .then(setSessions)
      .catch(() => setSessions([]));
  }, []);

  if (error) {
    return (
      <div className="dashboard-shell">
        <p className="dashboard-error">{error}</p>
      </div>
    );
  }

  const scored = sessions.filter((s) => s.overall_score != null);
  const averageScore = scored.length
    ? Math.round(scored.reduce((sum, s) => sum + s.overall_score, 0) / scored.length)
    : null;
  const streak = practiceStreak(scored);
  // Oldest-to-newest, so the sparkline reads left to right.
  const trend = scored.slice(0, 12).reverse();
  const best = scored.length ? Math.max(...scored.map((s) => s.overall_score)) : null;

  const summary = scored.length
    ? `You've completed ${scored.length} session${scored.length === 1 ? "" : "s"}, averaging ${averageScore}${
        best != null ? ` - your best so far is ${Math.round(best)}` : ""
      }.`
    : "You haven't practised yet - your first session takes about ten minutes.";

  return (
    <div className="dashboard-shell">
      <AppHeader />

      {notice && (
        <div className="dashboard-notice">
          <Notice title="Session not saved.">
            {notice}{" "}
            <button type="button" className="dashboard-notice__dismiss" onClick={() => setNotice(null)}>
              Dismiss
            </button>
          </Notice>
        </div>
      )}

      <div className="dashboard-header">
        <div className="avatar avatar--lg">{user ? initials(user.name) : "..."}</div>
        <div>
          <p className="dashboard-header__date">{TODAY}</p>
          <h1 className="dashboard-header__greeting">
            Welcome back{user ? `, ${firstName(user.name)}` : ""}
          </h1>
          <p className="dashboard-header__summary">{summary}</p>
        </div>
      </div>

      <section className="cta-banner">
        <div className="cta-banner__glow" aria-hidden="true" />
        <div className="cta-banner__body">
          <p className="bento-tile__eyebrow">Ready when you are</p>
          <h2>Start a mock interview</h2>
          <p className="bento-tile__meta">
            Pick a role, and ARIA will adapt the difficulty to how you're doing.
          </p>
        </div>
        <button className="bento-cta__button" onClick={() => navigate("/setup")}>
          Start interview →
        </button>
      </section>

      <div className="bento">
        <section className="bento-tile bento-tile--stat">
          <IconChip tint="accent">
            <CheckCircleIcon />
          </IconChip>
          <p className="bento-tile__eyebrow">Sessions completed</p>
          <p className={`bento-stat__value${scored.length > 0 ? " gradient-text" : " bento-stat__value--muted"}`}>
            {scored.length}
          </p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <IconChip tint="signal">
            <TargetIcon />
          </IconChip>
          <p className="bento-tile__eyebrow">Average score</p>
          <p className={`bento-stat__value${averageScore == null ? " bento-stat__value--muted" : " gradient-text"}`}>
            {averageScore ?? " - "}
          </p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <IconChip tint="accent">
            <FlameIcon />
          </IconChip>
          <p className="bento-tile__eyebrow">Practice streak</p>
          <p className={`bento-stat__value${streak === 0 ? " bento-stat__value--muted" : " gradient-text"}`}>
            {streak === 0 ? " - " : `${streak}d`}
          </p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <IconChip tint="signal">
            <CalendarIcon />
          </IconChip>
          <p className="bento-tile__eyebrow">Last session</p>
          <p className={`bento-stat__value bento-stat__value--small${scored.length === 0 ? " bento-stat__value--muted" : ""}`}>
            {scored.length ? new Date(scored[0].started_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : " - "}
          </p>
        </section>

        <section className="bento-tile bento-tile--history">
          <p className="bento-tile__eyebrow">Recent sessions</p>
          {scored.length === 0 ? (
            <div className="bento-empty">
              <p>No interviews yet.</p>
              <p className="bento-tile__meta">
                Your session history and feedback will show up here.
              </p>
            </div>
          ) : (
            <ul className="session-list">
              {scored.slice(0, 6).map((s) => (
                <li key={s.id}>
                  <Link
                    to="/report"
                    state={{ sessionId: s.id }}
                    className="session-list__row"
                  >
                    <span className="session-list__score">{Math.round(s.overall_score)}</span>
                    <span className="session-list__body">
                      <span className="session-list__role">{getRole(s.role).short}</span>
                      <span className="session-list__meta">
                        {s.mode === "conversation" ? "Conversation · " : ""}
                        {s.questions.filter((q) => q.content_score != null).length} answered ·{" "}
                        {new Date(s.started_at).toLocaleDateString()}
                      </span>
                    </span>
                    <span className="session-list__chevron" aria-hidden="true">
                      →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bento-tile bento-tile--progress">
          <p className="bento-tile__eyebrow">Progress over time</p>
          {trend.length < 2 ? (
            <div className="bento-empty bento-empty--chart">
              <div className="bento-empty__sparkline" aria-hidden="true">
                {Array.from({ length: 12 }).map((_, i) => (
                  <span key={i} />
                ))}
              </div>
              <p className="bento-tile__meta">Trends appear after your first few sessions.</p>
            </div>
          ) : (
            <div className="trend">
              <div className="trend__bars">
                {trend.map((s) => (
                  <span
                    key={s.id}
                    className="trend__bar"
                    style={{ height: `${Math.max(6, s.overall_score)}%` }}
                    title={`${Math.round(s.overall_score)} · ${new Date(
                      s.started_at
                    ).toLocaleDateString()}`}
                  />
                ))}
              </div>
              <div className="trend__baseline" aria-hidden="true" />
              <p className="bento-tile__meta">
                Last {trend.length} sessions · newest on the right
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
