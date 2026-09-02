import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getCurrentUser, clearTokens } from "../api/auth";
import Logo from "../components/Logo";
import "./Dashboard.css";

function initials(name) {
  return name
    .split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .catch(() => setError("Could not load your profile — please log in again."));
  }, []);

  const handleLogout = () => {
    clearTokens();
    navigate("/login");
  };

  if (error) {
    return (
      <div className="dashboard-shell">
        <p className="dashboard-error">{error}</p>
      </div>
    );
  }

  return (
    <div className="dashboard-shell">
      <header className="dashboard-header">
        <div className="dashboard-header__mark">
          <Logo size={24} />
          <span>ARIA</span>
        </div>
        <button className="dashboard-header__logout" onClick={handleLogout}>
          Log out
        </button>
      </header>

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
              Pick a role, and ARIA will adapt the difficulty to how you're doing in real time.
            </p>
          </div>
          <button className="bento-cta__button" disabled title="Interview flow ships next milestone">
            Start interview
            <span className="bento-cta__soon">Coming soon</span>
          </button>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Sessions completed</p>
          <p className="bento-stat__value">0</p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Average score</p>
          <p className="bento-stat__value bento-stat__value--muted">—</p>
        </section>

        <section className="bento-tile bento-tile--stat">
          <p className="bento-tile__eyebrow">Practice streak</p>
          <p className="bento-stat__value bento-stat__value--muted">—</p>
        </section>

        <section className="bento-tile bento-tile--history">
          <p className="bento-tile__eyebrow">Recent sessions</p>
          <div className="bento-empty">
            <p>No interviews yet.</p>
            <p className="bento-tile__meta">Your session history and feedback will show up here.</p>
          </div>
        </section>

        <section className="bento-tile bento-tile--progress">
          <p className="bento-tile__eyebrow">Progress over time</p>
          <div className="bento-empty bento-empty--chart">
            <div className="bento-empty__sparkline" aria-hidden="true">
              {Array.from({ length: 12 }).map((_, i) => (
                <span key={i} />
              ))}
            </div>
            <p className="bento-tile__meta">Trends appear after your first few sessions.</p>
          </div>
        </section>
      </div>
    </div>
  );
}
