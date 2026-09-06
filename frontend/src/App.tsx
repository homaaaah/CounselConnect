import { useEffect, useState } from "react";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import HomePage from "./pages/HomePage";
import ReviewerPage from "./pages/ReviewerPage";
import { useHealth } from "./hooks/useHealth";
import { useSession } from "./features/auth";

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

  return (
    <>
      {session.error && <p role="alert" className="p-3 text-red-700">{session.error}</p>}
      {session.user && (
        <div className="flex justify-end bg-white px-6 py-2">
          <button onClick={async () => {
            if (await session.logout()) window.location.hash = "landing";
          }} className="text-sm text-slate-600 underline">Sign out</button>
        </div>
      )}
      {page === "login" && <LoginPage onSignedIn={session.accept} />}
      {page === "register" && <RegisterPage />}
      {page === "home" && <HomePage />}
      {page === "review" && (session.user?.role_code === "COUNSELOR"
        ? <ReviewerPage />
        : session.user
          ? <p role="alert" className="p-6">This page requires a Counselor account.</p>
          : <LoginPage onSignedIn={session.accept} />)}
      {!["login", "register", "home", "review"].includes(page) && (
        <LandingPage onPreviewHome={() => (window.location.hash = "home")} />
      )}
      <p className="fixed bottom-2 right-3 text-[10px] text-slate-300">
        {error ? `API unreachable: ${error}` : `API status: ${status}`}
      </p>
    </>
  );
}
