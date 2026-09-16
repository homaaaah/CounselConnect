import { useEffect, useState } from "react";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import StudentHomePage from "./pages/student/student_homepage";
import CounselorDashboard from "./pages/counselor/counselor_dashboard";
import ReviewerPage from "./pages/ReviewerPage";
import StudentAppointmentsPage from "./pages/student/StudentAppointmentsPage";
import CounselorAppointmentsPage from "./pages/counselor/CounselorAppointmentsPage";
import { useHealth } from "./hooks/useHealth";
import { useSession } from "./features/auth";
import { AppNavBar } from "./components/layout";
import ScheduledSessionPage from "./pages/ScheduledSessionPage";
import { ScheduledSessionLauncher } from "./features/messaging";

function SessionExpiryWarning({ session }) {
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  if (!session.user) return null;
  const deadline = Math.min(
    new Date(session.idleExpiresAt).getTime(),
    new Date(session.absoluteExpiresAt).getTime(),
  );
  const remaining = deadline - now;
  if (!Number.isFinite(deadline) || remaining > 5 * 60_000 || remaining <= 0) return null;
  return <div role="alert" className="fixed inset-x-4 top-4 z-50 mx-auto max-w-xl rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-lg">
    <p className="font-semibold text-amber-900">Your session expires in {Math.max(1, Math.ceil(remaining / 60000))} minute(s).</p>
    <button type="button" disabled={busy} className="mt-2 rounded-lg bg-amber-800 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
      onClick={async () => { setBusy(true); try { await session.continueSession(); } catch { /* global 401 handling clears an expired session */ } finally { setBusy(false); } }}>
      Continue session
    </button>
  </div>;
}

/**
 * Hash-based page switcher (DFD Master System Flow).
 * The reviewer UI mounts only after cookie/CSRF restoration and a role
 * check. The backend independently authorizes every protected request.
 */
export default function App() {
  const [page, setPage] = useState(window.location.hash.replace("#", "") || "landing");
  const { status, error } = useHealth();
  const session = useSession();

  useEffect(() => { void session.restore(); }, [session.restore]);

  useEffect(() => {
    const onHash = () => setPage(window.location.hash.replace("#", "") || "landing");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (!session.ready) {
    return <p role="status" className="p-6">Restoring your session…</p>;
  }

  // Counselor shell: fixed left sidebar on desktop — page content shifts
  // right by the sidebar width (16rem) so nothing hides underneath it.
  const counselorShell = session.user?.role_code === "COUNSELOR";
  const sessionAppointmentId = page.startsWith("session/") ? Number(page.slice("session/".length)) : null;

  return (
    <>
      {session.error && <p role="alert" className="p-3 text-red-700">{session.error}</p>}
      {session.user && (
        <AppNavBar
          user={session.user}
          page={page}
          onSignOut={async () => {
            if (await session.logout()) window.location.hash = "landing";
          }}
        />
      )}
      <div className={counselorShell ? "lg:ml-64" : undefined}>
        {page === "login" && <LoginPage onSignedIn={session.accept} />}
        {page === "staff-login" && <LoginPage audience="staff" onSignedIn={session.accept} />}
        {page === "register" && <RegisterPage />}
        {page === "home" && (session.user
          ? session.user.role_code === "COUNSELOR"
            ? <CounselorDashboard user={session.user} />
            : <StudentHomePage user={session.user} />
          : <StudentHomePage user={null} />)}
        {page === "appointments" && (session.user
          ? session.user.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code)
            ? session.user.role_code === "COUNSELOR"
              ? <CounselorAppointmentsPage key={session.user.user_id} user={session.user} />
              : <StudentAppointmentsPage key={session.user.user_id} user={session.user} />
            : <p role="alert" className="p-6">Appointments require an active Student or Counselor account.</p>
          : <LoginPage onSignedIn={session.accept} />)}
        {page === "review" && (["COUNSELOR", "GUIDANCE_STAFF"].includes(session.user?.role_code)
          ? <ReviewerPage user={session.user} />
          : session.user
            ? <p role="alert" className="p-6">This page requires a Counselor or Guidance Staff account.</p>
            : <LoginPage audience="staff" onSignedIn={session.accept} />)}
        {sessionAppointmentId && session.user?.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code) &&
          <ScheduledSessionPage key={`${session.user.user_id}-${sessionAppointmentId}`} user={session.user} appointmentId={sessionAppointmentId} />}
        {!["login", "staff-login", "register", "home", "review", "appointments"].includes(page) && !sessionAppointmentId && (
          <LandingPage onSignedIn={session.accept} />
        )}
      </div>
      {session.user?.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code) &&
        <ScheduledSessionLauncher key={session.user.user_id} user={session.user} />}
      <SessionExpiryWarning session={session} />
      <p className="fixed bottom-2 right-3 text-[10px] text-slate-300">
        {error ? `API unreachable: ${error}` : `API status: ${status}`}
      </p>
    </>
  );
}
