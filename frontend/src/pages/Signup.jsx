import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { signup, storeTokens } from "../api/auth";
import BrandPanel from "../components/BrandPanel";
import FormField from "../components/FormField";
import Logo from "../components/Logo";
import "./Auth.css";

export default function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
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
      const tokens = await signup(form);
      storeTokens(tokens);
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <BrandPanel />
      <div className="auth-form-side">
        <div className="auth-card">
          <div className="auth-card__mobile-mark">
            <Logo size={24} />
            <span>ARIA</span>
          </div>
          <h2>Create your account</h2>
          <p className="auth-card__lede">Start practicing in under a minute.</p>

          <form onSubmit={handleSubmit} noValidate>
            <FormField
              label="Name"
              name="name"
              autoComplete="name"
              value={form.name}
              onChange={handleChange}
              required
            />
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
              autoComplete="new-password"
              minLength={8}
              value={form.password}
              onChange={handleChange}
              required
            />
            {error && <p className="auth-alert">{error}</p>}
            <button type="submit" className="auth-submit" disabled={loading}>
              {loading && <span className="auth-submit__spinner" />}
              {loading ? "Creating account..." : "Sign up"}
            </button>
          </form>

          <p className="auth-switch">
            Already have an account? <Link to="/login">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
