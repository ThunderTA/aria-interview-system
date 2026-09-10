import { Link, useNavigate } from "react-router-dom";
import { clearTokens } from "../api/auth";
import Logo from "./Logo";
import "./AppHeader.css";

/**
 * `onNavigateAttempt`, if provided, intercepts every navigation this header
 * can trigger (logo-home, back link, logout) and is handed a callback that
 * performs the real navigation. Pages with something at stake if you leave
 * mid-flow — Interview, mid-session — pass one that shows a confirmation and
 * only invokes the callback once the candidate has actually agreed to leave;
 * everywhere else, omitting the prop keeps navigation immediate as before.
 */
export default function AppHeader({ backTo, backLabel = "Back", onNavigateAttempt }) {
  const navigate = useNavigate();

  const go = (path) => () => {
    const proceed = () => navigate(path);
    if (onNavigateAttempt) onNavigateAttempt(proceed);
    else proceed();
  };

  const handleLogout = () => {
    const proceed = () => {
      clearTokens();
      navigate("/login");
    };
    if (onNavigateAttempt) onNavigateAttempt(proceed);
    else proceed();
  };

  // Real <Link>s (correct href, middle-click/cmd-click open in a new tab)
  // when unguarded; guarded pages intercept the click and route through the
  // confirmation instead of navigating immediately.
  const linkProps = (path) =>
    onNavigateAttempt
      ? {
          onClick: (e) => {
            e.preventDefault();
            go(path)();
          },
        }
      : {};

  return (
    <header className="app-header">
      <div className="app-header__left">
        <Link to="/dashboard" className="app-header__mark" {...linkProps("/dashboard")}>
          <Logo size={24} />
          <span>ARIA</span>
        </Link>
        {backTo && (
          <Link to={backTo} className="app-header__back" {...linkProps(backTo)}>
            ← {backLabel}
          </Link>
        )}
      </div>
      <button className="app-header__logout" onClick={handleLogout}>
        Log out
      </button>
    </header>
  );
}
