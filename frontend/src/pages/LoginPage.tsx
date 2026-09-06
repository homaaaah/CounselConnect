import { useEffect, useState } from "react";
import { useLogin, type AuthResult } from "../features/auth";

/** Sign-in page (ADR-019): opaque session cookie + CSRF. */
export default function LoginPage({ onSignedIn }: { onSignedIn: (auth: AuthResult) => void }) {
  const { login, submitting } = useLogin();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<{ ok: boolean; message: string; role?: string } | null>(null);

  useEffect(() => {
    if (result?.ok && result.role) {
      // Route by role: counselors land on the review console.
      const target = result.role === "COUNSELOR" ? "#review" : "#landing";
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

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-md rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-800">Sign in</h1>
        <p className="mt-1 text-sm text-slate-500">
          CounselConnect — Guidance and Counseling Office
        </p>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="identifier" className="text-sm font-medium text-slate-700">
              Student number or email
            </label>
            <input
              id="identifier"
              type="text"
              required
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="password" className="text-sm font-medium text-slate-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {result && (
          <p
            className={`mt-4 rounded-md p-3 text-sm ${
              result.ok
                ? "bg-emerald-50 text-emerald-700"
                : "bg-red-50 text-red-600"
            }`}
          >
            {result.message}
          </p>
        )}

        <p className="mt-6 text-center text-sm text-slate-500">
          No account yet?{" "}
          <a href="#register" className="font-medium text-emerald-600 hover:underline">
            Register
          </a>
        </p>
        <p className="mt-2 text-center text-xs text-slate-400">
          <a href="#landing" className="hover:underline">
            Back to landing page
          </a>
        </p>
      </div>
    </main>
  );
}
