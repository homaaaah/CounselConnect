import { useEffect, useState } from "react";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import HomePage from "./pages/HomePage";
import ReviewerPage from "./pages/ReviewerPage";
import { useHealth } from "./hooks/useHealth";

/**
 * Hash-based page switcher (DFD Master System Flow).
 * A real protected router arrives with ADR-P01; until then the four pages
 * exist and the health line proves the full stack round-trip.
 */
export default function App() {
  const [page, setPage] = useState(window.location.hash.replace("#", "") || "landing");
  const { status, error } = useHealth();

  useEffect(() => {
    const onHash = () => setPage(window.location.hash.replace("#", "") || "landing");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <>
      {page === "login" && <LoginPage />}
      {page === "register" && <RegisterPage />}
      {page === "home" && <HomePage />}
      {page === "review" && <ReviewerPage />}
      {!["login", "register", "home", "review"].includes(page) && (
        <LandingPage onPreviewHome={() => (window.location.hash = "home")} />
      )}
      <p className="fixed bottom-2 right-3 text-[10px] text-slate-300">
        {error ? `API unreachable: ${error}` : `API status: ${status}`}
      </p>
    </>
  );
}
