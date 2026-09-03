import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { login, storeTokens } from "../api/auth";
import BrandPanel from "../components/BrandPanel";
import FormField from "../components/FormField";
import Logo from "../components/Logo";
import "./Auth.css";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await login(form);
      storeTokens(tokens);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <BrandPanel />
      <div className="auth-form-side">
        <div className="auth-card">
          <Link to="/" className="auth-card__mobile-mark">
            <Logo size={24} />
            <span>ARIA</span>
          </Link>
          <h2>Welcome back</h2>
          <p className="auth-card__lede">Log in to continue practicing.</p>

          <form onSubmit={handleSubmit} noValidate>
            <FormField
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={handleChange}
              required
            />
            <FormField
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={form.password}
              onChange={handleChange}
              required
            />
            {error && <p className="auth-alert">{error}</p>}
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading && <span className="auth-submit__spinner" />}
              {loading ? "Logging in..." : "Log in"}
            </button>
          </form>

          <p className="auth-switch">
            Don't have an account? <Link to="/signup">Sign up</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
