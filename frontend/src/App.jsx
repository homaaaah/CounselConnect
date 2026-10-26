import { useEffect, useState } from "react";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import StudentHomePage from "./pages/student/student_homepage";
import CounselorDashboard from "./pages/counselor/counselor_dashboard";
import CounselorUsersPage from "./pages/counselor/CounselorUsersPage";
import UsersManagementPage from "./pages/superadmin/UsersManagementPage";
import CorrectionsPage from "./pages/superadmin/CorrectionsPage";
import RegistrationStatusPage from "./pages/student/RegistrationStatusPage";
import StudentAppointmentsPage from "./pages/student/StudentAppointmentsPage";
import CounselorAppointmentsPage from "./pages/counselor/CounselorAppointmentsPage";
import CounselorSchedulePage from "./pages/counselor/CounselorSchedulePage";
import CounselorHistoryPage from "./pages/counselor/CounselorHistoryPage";
import { useHealth } from "./hooks/useHealth";
import { useSession } from "./features/auth";
import { AppNavBar } from "./components/layout";
import { ToastProvider, useToast } from "./components/feedback";
import { setErrorHandler } from "./services/apiClient";
import ScheduledSessionPage from "./pages/ScheduledSessionPage";
import SessionRecordPage from "./pages/SessionRecordPage";
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
 * Protected pages mount only after cookie/CSRF restoration and a role
 * check. The backend independently authorizes every protected request.
 */
export default function App() {
  return (
    <ToastProvider>
      <AppShell />
    </ToastProvider>
  );
}

function AppShell() {
  const landingSections = new Set(["features", "news", "faq", "counselors"]);
  const currentHashPage = () => {
    const hash = window.location.hash.replace("#", "") || "landing";
    return landingSections.has(hash) ? "landing" : hash;
  };
  const [page, setPage] = useState(currentHashPage);
  const { status, error } = useHealth();
  const session = useSession();
  const toast = useToast();

  useEffect(() => {
    const onAppointmentToast = (event) => {
      toast.success(event.detail?.message || "An appointment was updated.", { title: "Appointment update" });
    };
    window.addEventListener("counselconnect-toast", onAppointmentToast);
    return () => window.removeEventListener("counselconnect-toast", onAppointmentToast);
  }, [toast.success]);

  useEffect(() => { void session.restore(); }, [session.restore]);

  // Re-read the signed-in user when the window regains focus so database
  // edits (name, status) appear without a full reload.
  const signedInUserId = session.user?.user_id ?? null;
  useEffect(() => {
    if (!signedInUserId) return undefined;
    const revalidate = () => { void session.refresh(); };
    const onVisibility = () => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") revalidate();
    };
    window.addEventListener("focus", revalidate);
    if (typeof document !== "undefined") document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", revalidate);
      if (typeof document !== "undefined") document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [signedInUserId, session.refresh]);

  // Surface every failed API request as a visual notification.
  useEffect(() => {
    setErrorHandler((apiError) => toast.error(apiError.message, { title: "Request failed" }));
    return () => setErrorHandler(null);
  }, [toast.error]);

  useEffect(() => {
    if (session.error) toast.error(session.error, { title: "Session" });
  }, [session.error, toast.error]);

  useEffect(() => {
    if (error) toast.error(`API unreachable: ${error}`, { title: "Connection" });
  }, [error, toast.error]);

  // Rejecting the extracted details signs the Student out so they can start over.
  const handleRejected = async () => {
    try { await session.logout(); } catch { /* ignore; redirect anyway */ }
    window.location.hash = "login";
  };

  useEffect(() => {
    const onHash = () => setPage(currentHashPage());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  if (!session.ready) {
    return <p role="status" className="p-6">Restoring your session…</p>;
  }

  const sessionAppointmentId = page.startsWith("session/") ? Number(page.slice("session/".length)) : null;
  const recordAppointmentId = page.startsWith("session-record/") ? Number(page.slice("session-record/".length)) : null;

  return (
    <>
      {session.error && <p role="alert" className="p-3 text-red-700">{session.error}</p>}
      <div className="flex h-[100dvh] flex-col">
        {session.user && (
          <AppNavBar
            user={session.user}
            page={page}
            onSignOut={async () => {
              if (await session.logout()) window.location.hash = "landing";
            }}
          />
        )}
        <div className="min-h-0 flex-1">
        {page === "login" && <LoginPage onSignedIn={session.accept} />}
        {page === "staff-login" && <LoginPage audience="staff" onSignedIn={session.accept} />}
        {page === "register" && <RegisterPage />}
        {page === "home" && (session.user
          ? session.user.role_code === "SUPERADMIN"
            ? <UsersManagementPage user={session.user} />
            : session.user.role_code === "COUNSELOR"
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
        {page === "registration" && (session.user?.role_code === "STUDENT"
          ? <RegistrationStatusPage key={session.user.user_id} user={session.user} onRejected={handleRejected} onEnrollmentChanged={session.continueSession} />
          : <LoginPage onSignedIn={session.accept} />)}
        {page === "schedule" && (session.user?.role_code === "COUNSELOR"
          ? <CounselorSchedulePage key={session.user.user_id} user={session.user} />
          : <LoginPage onSignedIn={session.accept} />)}
        {page === "history" && (session.user?.role_code === "COUNSELOR"
          ? <CounselorHistoryPage key={session.user.user_id} user={session.user} />
          : <LoginPage onSignedIn={session.accept} />)}
        {page === "users" && (session.user?.role_code === "SUPERADMIN"
          ? <UsersManagementPage user={session.user} />
          : <LoginPage onSignedIn={session.accept} />)}
        {page === "corrections" && (session.user?.role_code === "SUPERADMIN"
          ? <CorrectionsPage key={session.user.user_id} /> : <LoginPage onSignedIn={session.accept} />)}
        {page === "student-directory" && (session.user?.role_code === "SUPERADMIN"
          ? <CounselorUsersPage canRecover showCorrections={false} /> : <LoginPage onSignedIn={session.accept} />)}
        {sessionAppointmentId && session.user?.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code) &&
          <ScheduledSessionPage key={`${session.user.user_id}-${sessionAppointmentId}`} user={session.user} appointmentId={sessionAppointmentId} />}
        {recordAppointmentId && session.user?.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code) &&
          <SessionRecordPage key={`${session.user.user_id}-record-${recordAppointmentId}`} user={session.user} appointmentId={recordAppointmentId} />}
        {!["login", "staff-login", "register", "registration", "users", "corrections", "student-directory", "home", "appointments", "schedule", "history"].includes(page) && !sessionAppointmentId && !recordAppointmentId && (
          <LandingPage
            onSignedIn={session.accept}
          />
        )}
      </div>
      </div>
      {session.user?.account_status === "ACTIVE" && ["STUDENT", "COUNSELOR"].includes(session.user.role_code) && !sessionAppointmentId &&
        <ScheduledSessionLauncher key={session.user.user_id} user={session.user} />}
      <SessionExpiryWarning session={session} />
      <p className="fixed bottom-2 right-3 text-[10px] text-slate-600">
        {error ? `API unreachable: ${error}` : `API status: ${status}`}
      </p>
    </>
  );
}
