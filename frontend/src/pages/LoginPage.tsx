import { useEffect, useState } from "react";
import { useLogin, type AuthResult } from "../features/auth";

/**
 * Sign-in page (ADR-019): opaque session cookie + CSRF. Capstone card styling.
 * inModal renders the same card without the full-page shell, with in-modal
 * audience/register switches and a close button (landing overlay).
 */
export default function LoginPage({ onSignedIn, audience = "student", inModal = false,
  onClose, onSwitchAudience, onSwitchToRegister }: {
  onSignedIn: (auth: AuthResult) => void;
  audience?: "student" | "staff";
  inModal?: boolean;
  onClose?: () => void;
  onSwitchAudience?: () => void;
  onSwitchToRegister?: () => void;
}) {
  const isStudent = audience === "student";
  const { login, submitting } = useLogin();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message: string; role?: string } | null>(null);

  useEffect(() => {
    if (result?.ok && result.role) {
      // Route by role: counselors land on the review console.
      const target = result.role === "COUNSELOR" ? "#review" : result.role === "STUDENT" ? "#home" : "#landing";
      const t = setTimeout(() => {
        window.location.hash = target;
      }, 700);
      return () => clearTimeout(t);
    }
  }, [result]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const r = await login(identifier, password);
    if (r.ok && r.auth) onSignedIn(r.auth);
    setResult({ ok: r.ok, message: r.message, role: r.auth?.user.role_code });
  }

  const card = (
    <div className="modal-card">
      {inModal && (
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
          <i className="fa-solid fa-xmark"></i>
        </button>
      )}

      <div className="login-header">
        <h1>{isStudent ? "Student sign in" : "Counselor / Staff sign in"}</h1>
        <p>CounselConnect — Guidance and Counseling Office</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="identifier">{isStudent ? "Student number" : "Email"}</label>
          <input
            id="identifier"
            type={isStudent ? "text" : "email"}
            autoComplete="username"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            className="form-input"
          />
        </div>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="form-input"
          />
        </div>
        <button type="submit" disabled={submitting} className="btn-submit">
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      {result && <div className={`form-message ${result.ok ? "success" : "error"}`} role="status">{result.message}</div>}

      {inModal ? (
        <>
          <p className="signup-text">
            <button type="button" className="linklike" onClick={onSwitchAudience}>
              {isStudent ? "Counselor / Staff sign in" : "Student sign in"}
            </button>
          </p>
          <p className="signup-text">
            No account yet? <button type="button" className="linklike" onClick={onSwitchToRegister}>Register</button>
          </p>
        </>
      ) : (
        <>
          <p className="signup-text">
            <a href={isStudent ? "#staff-login" : "#login"}>
              {isStudent ? "Counselor / Staff sign in" : "Student sign in"}
            </a>
          </p>
          <p className="signup-text">
            No account yet? <a href="#register">Register</a>
          </p>
          <p className="footer-link" style={{ textAlign: "center" }}>
            <a href="#landing">Back to landing page</a>
          </p>
        </>
      )}
    </div>
  );

  return inModal ? card : <main className="auth-shell">{card}</main>;
}
