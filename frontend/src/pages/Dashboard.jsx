import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getCurrentUser } from "../api/auth";
import { listSessions } from "../api/sessions";
import AppHeader from "../components/AppHeader";
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

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch(() => setError("Could not load your profile — please log in again."));
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

  return (
    <div className="dashboard-shell">
      <AppHeader />

      <div className="bento">
        <section className="bento-tile bento-tile--welcome">
          <div className="avatar">{user ? initials(user.name) : "…"}</div>
          <div>
            <p className="bento-tile__eyebrow">Signed in as</p>
            <h3>{user ? user.name : "Loading..."}</h3>
            <p className="bento-tile__meta">{user?.email}</p>
          </div>
        </section>

        <section className="bento-tile bento-tile--cta">
          <div>
            <p className="bento-tile__eyebrow">Ready when you are</p>
            <h2>Start a mock interview</h2>
            <p className="bento-tile__meta">
              Pick a role, and ARIA will adapt the difficulty to how you're doing.
            </p>
          </div>
          <div className="bento-cta__actions">
            <button className="bento-cta__button" onClick={() => navigate("/setup")}>
              Start interview
            </button>
          </div>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Sessions completed</p>
          <p className={`bento-stat__value${scored.length > 0 ? " gradient-text" : " bento-stat__value--muted"}`}>
            {scored.length}
          </p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Average score</p>
          <p className={`bento-stat__value${averageScore == null ? " bento-stat__value--muted" : " gradient-text"}`}>
            {averageScore ?? "—"}
          </p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Practice streak</p>
          <p className={`bento-stat__value${streak === 0 ? " bento-stat__value--muted" : " gradient-text"}`}>
            {streak === 0 ? "—" : `${streak}d`}
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
