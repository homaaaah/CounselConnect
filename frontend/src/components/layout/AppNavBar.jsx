/**
 * AppNavBar — signed-in app shell navigation (role-aware menu).
 *
 * Role visibility here is usability only; backend authorization
 * is authoritative (docs/USER_ROLES.md). Coming-soon entries are
 * non-navigable placeholders; the session pill is a passive display
 * (ADR-019) — the 401 path in apiClient handles real expiry, and the
 * 60s background poll never renews idle activity (X-Background-Refresh).
 */

import { useEffect, useMemo, useState } from "react";
import { request } from "../../services/apiClient";

const COMING_SOON = ["Messages", "SOS", "Resources", "Assistant"];

const roleLabel = (code) =>
  code === "COUNSELOR" ? "Counselor" : code === "GUIDANCE_STAFF" ? "Guidance Staff" : "Student";

const timeFormatter = new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila",
  hour: "numeric",
  minute: "2-digit",
});

/** Earlier of idle/absolute expiry; null when both are absent. */
function earliestExpiry(idle, absolute) {
  if (idle && absolute) return idle <= absolute ? idle : absolute;
  return idle ?? absolute;
}

export default function AppNavBar({ user, page, idleExpiresAt, absoluteExpiresAt, onSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [syncedIdle, setSyncedIdle] = useState(idleExpiresAt);
  const [syncedAbsolute, setSyncedAbsolute] = useState(absoluteExpiresAt);
  const [tick, setTick] = useState(0);

  useEffect(() => { setSyncedIdle(idleExpiresAt); setSyncedAbsolute(absoluteExpiresAt); },
    [idleExpiresAt, absoluteExpiresAt]);

  // Passive re-sync: GET /auth/csrf never renews idle activity because it is
  // sent with X-Background-Refresh: 1 (backend ignores it for activity).
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const auth = await request("/auth/csrf", { headers: { "X-Background-Refresh": "1" } });
        if (!cancelled) { setSyncedIdle(auth.idle_expires_at); setSyncedAbsolute(auth.absolute_expires_at); }
      } catch { /* keep last known values; the 401 path handles real expiry */ }
    };
    const syncTimer = setInterval(() => { void poll(); }, 60_000);
    const tickTimer = setInterval(() => { setTick((n) => n + 1); }, 30_000);
    return () => { cancelled = true; clearInterval(syncTimer); clearInterval(tickTimer); };
  }, []);

  const { pillText, pillAmber } = useMemo(() => {
    void tick;
    const endsAt = earliestExpiry(syncedIdle, syncedAbsolute);
    if (!endsAt) return { pillText: null, pillAmber: false };
    const minutes = Math.floor((new Date(endsAt).getTime() - Date.now()) / 60_000);
    const amber = minutes >= 0 && minutes <= 5;
    const text = amber
      ? `Session ends in ${minutes < 1 ? "<1m" : minutes + "m"}`
      : `Session ends ${timeFormatter.format(new Date(endsAt))}`;
    return { pillText: text, pillAmber: amber };
  }, [syncedIdle, syncedAbsolute, tick]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const links = [{ label: "Home", href: "#home" }];
  const activeStudent = user.role_code === "STUDENT" && user.account_status === "ACTIVE";
  if (activeStudent || user.role_code === "COUNSELOR") links.push({ label: "Appointments", href: "#appointments" });
  if (user.role_code === "COUNSELOR") links.push({ label: "COR Verification", href: "#review" });
  const showComingSoon = user.role_code === "STUDENT" || user.role_code === "COUNSELOR";

  const linkClass = (href) => {
    const current = href === "#" + page;
    return "px-1 py-4 text-sm font-medium transition-colors " +
      (current
        ? "border-b-2 border-emerald-600 text-emerald-700"
        : "border-b-2 border-transparent text-slate-600 hover:text-emerald-700");
  };

  const bannerText = user.role_code !== "STUDENT" || user.account_status === "ACTIVE" ? null
    : user.account_status === "PENDING_VERIFICATION"
      ? "Verification pending — scheduling unlocks after COR approval."
      : user.account_status === "VERIFICATION_EXPIRED"
        ? "Enrollment expired — re-verify your COR to restore scheduling."
        : "Scheduling is locked for your account status.";

  return (
    <>
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white">
        <nav aria-label="App navigation" className="mx-auto flex max-w-6xl items-center gap-4 px-4 sm:px-6">
          <a href="#home" className="py-2 text-base font-semibold tracking-tight text-emerald-800">CounselConnect</a>
          <div className="hidden items-center gap-5 md:flex">
            {links.map((link) => (
              <a key={link.href} href={link.href} className={linkClass(link.href)}
                {...(link.href === "#" + page ? { "aria-current": "page" } : {})}
                onClick={() => setMenuOpen(false)}>{link.label}</a>
            ))}
            {showComingSoon && COMING_SOON.map((label) => (
              <span key={label} aria-disabled="true" title="Coming soon"
                className="inline-flex cursor-default items-center gap-1 border-b-2 border-transparent px-1 py-4 text-sm text-slate-300">
                {label}
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>
              </span>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-3">
            {pillText && (
              <span className={"hidden items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium sm:inline-flex " +
                (pillAmber ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600")}
                title={pillAmber ? "Your session is about to end" : "Your session ends at this time (Asia/Manila)"}>
                <i className="fa-regular fa-clock" aria-hidden="true"></i>
                {pillText}
              </span>
            )}
            <span className="hidden items-center gap-2 sm:inline-flex">
              <span className="text-sm text-slate-700">
                {user.first_name} {user.last_name}
              </span>
              <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                {roleLabel(user.role_code)}
              </span>
              {user.role_code === "STUDENT" && user.account_status !== "ACTIVE" && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                  {user.account_status === "PENDING_VERIFICATION" ? "Verification pending" : "Verification expired"}
                </span>
              )}
            </span>
            <button type="button" onClick={onSignOut}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
              Sign out
            </button>
            <button type="button" className="md:hidden" aria-expanded={menuOpen} aria-controls="app-nav-links"
              aria-label={menuOpen ? "Close menu" : "Open menu"} onClick={() => setMenuOpen(!menuOpen)}>
              <i className={menuOpen ? "fa-solid fa-xmark" : "fa-solid fa-bars"} aria-hidden="true"></i>
            </button>
          </div>
        </nav>
        <div id="app-nav-links" hidden={!menuOpen}
          className="border-t border-slate-200 bg-white px-4 pb-3 md:hidden">
          {links.map((link) => (
            <a key={link.href} href={link.href} className={"block py-2.5 text-sm font-medium " +
              (link.href === "#" + page ? "text-emerald-700" : "text-slate-600")}
              {...(link.href === "#" + page ? { "aria-current": "page" } : {})}
              onClick={() => setMenuOpen(false)}>{link.label}</a>
          ))}
          {showComingSoon && COMING_SOON.map((label) => (
            <span key={label} aria-disabled="true" title="Coming soon"
              className="inline-flex cursor-default items-center gap-1 py-2.5 text-sm text-slate-300">
              {label}
              <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>
            </span>
          ))}
          {user.role_code === "STUDENT" && user.account_status !== "ACTIVE" && (
            <span className="mt-1 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              {user.account_status === "PENDING_VERIFICATION" ? "Verification pending" : "Verification expired"}
            </span>
          )}
          {pillText && (
            <span className={"mt-2 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium " +
              (pillAmber ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-600")}>
              {pillText}
            </span>
          )}
        </div>
      </header>
      {bannerText && (
        <div role="status" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-sm text-amber-800 sm:px-6">
          {bannerText}
        </div>
      )}
    </>
  );
}
