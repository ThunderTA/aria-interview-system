import { Link, useNavigate } from "react-router-dom";
import { clearTokens } from "../api/auth";
import Logo from "./Logo";
import "./AppHeader.css";

export default function AppHeader({ backTo, backLabel = "Back" }) {
  const navigate = useNavigate();

  const handleLogout = () => {
    clearTokens();
    navigate("/login");
  };

  return (
    <header className="app-header">
      <div className="app-header__left">
        <Link to="/dashboard" className="app-header__mark">
          <Logo size={24} />
          <span>ARIA</span>
        </Link>
        {backTo && (
          <Link to={backTo} className="app-header__back">
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
