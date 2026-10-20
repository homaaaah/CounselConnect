/**
 * AppNavBar — signed-in app shell navigation (role-aware).
 *
 * All signed-in roles share one top-bar header. Only the links and the
 * "coming soon" entries differ by role:
 *   - Counselor: Dashboard (#home), Appointments (#appointments); Sessions,
 *     Schedule and History have no routes yet, so they render as
 *     non-navigable "coming soon" placeholders.
 *   - Superadmin (ADR-030): Users only.
 *   - Guidance Staff: Home only.
 *   - Student: Home (#home), Appointments (#appointments); History and
 *     Session render as non-navigable "coming soon" placeholders.
 *
 * Role visibility here is usability only; backend authorization
 * is authoritative (docs/USER_ROLES.md). Real session expiry is
 * handled by the 401 path in apiClient (ADR-019) — the passive
 * session-ends indicator was removed (2026-09-12).
 */

import { useEffect, useState } from "react";

const roleLabel = (code) =>
  code === "COUNSELOR" ? "Counselor"
    : code === "GUIDANCE_STAFF" ? "Guidance Staff"
      : code === "SUPERADMIN" ? "Superadmin"
        : "Student";

/**
 * Role-based navigation for the shared top bar. `links` navigate; `comingSoon`
 * labels render as non-navigable placeholders until their features ship.
 */
function roleNav(user) {
  if (user.role_code === "COUNSELOR") {
    return {
      links: [
        { label: "Dashboard", href: "#home" },
        { label: "Appointments", href: "#appointments" },
      ],
      // No dedicated routes yet — shown in the nav but inactive for now.
      comingSoon: ["Sessions", "Schedule", "History"],
    };
  }
  if (user.role_code === "SUPERADMIN") {
    return { links: [{ label: "Users", href: "#users" }], comingSoon: [] };
  }
  if (user.role_code === "GUIDANCE_STAFF") {
    return { links: [{ label: "Home", href: "#home" }], comingSoon: [] };
  }
  return {
    links: [
      { label: "Home", href: "#home" },
      { label: "Appointments", href: "#appointments" },
    ],
    // No dedicated routes yet — shown in the nav but inactive for now.
    comingSoon: ["History", "Session"],
  };
}

export default function AppNavBar({ user, page, onSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return <TopBarNav user={user} page={page} onSignOut={onSignOut} menuOpen={menuOpen} setMenuOpen={setMenuOpen} />;
}

/* ---------------- Top bar (all signed-in roles) ---------------- */

function TopBarNav({ user, page, onSignOut, menuOpen, setMenuOpen }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const { links, comingSoon } = roleNav(user);
  const isStudent = user.role_code === "STUDENT";

  useEffect(() => {
    if (!profileOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setProfileOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [profileOpen]);

  const linkClass = (href) => {
    const current = href === "#" + page;
    return "px-1 py-4 text-sm font-medium transition-colors " +
      (current
        ? "border-b-2 border-counseling-active-focus text-zinc-900"
        : "border-b-2 border-transparent text-zinc-900 hover:text-counseling-active-focus");
  };

  const bannerText = user.role_code !== "STUDENT" || user.account_status === "ACTIVE" ? null
    : user.account_status === "PENDING_VERIFICATION"
      ? "Verification pending — confirm your COR details to unlock scheduling."
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
            {comingSoon.map((label) => (
              <span key={label} aria-disabled="true" title="Coming soon"
                className="inline-flex cursor-default items-center gap-1 border-b-2 border-transparent px-1 py-4 text-sm text-slate-300">
                {label}
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>
              </span>
            ))}
          </div>
          <div className={isStudent ? "ml-auto relative flex items-center gap-3" : "ml-auto flex items-center gap-3"}>
            {isStudent ? (
              <>
                <button type="button" aria-expanded={profileOpen} aria-label="Open profile menu"
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 p-1.5 text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-counseling-active-focus">
                  <i className="fa-solid fa-user-circle text-2xl text-slate-600" aria-hidden="true"></i>
                  <span className="hidden text-sm font-medium sm:inline pr-1">{user.first_name}</span>
                </button>

                <div hidden={!profileOpen} className="absolute right-0 top-12 z-50 w-64 rounded-xl border border-slate-200 bg-white p-4 shadow-lg">
                  <div className="border-b border-slate-100 pb-3">
                    <p className="text-sm font-semibold text-slate-900">{user.first_name} {user.last_name}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                        {roleLabel(user.role_code)}
                      </span>
                      {user.account_status !== "ACTIVE" && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                          {user.account_status === "PENDING_VERIFICATION" ? "Verification pending" : "Verification expired"}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="py-2 border-b border-slate-100 my-1">
                    <span aria-disabled="true" title="Coming soon"
                      className="flex cursor-default items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-400">
                      <span className="flex items-center gap-2">
                        <i className="fa-solid fa-gear w-4 text-center" aria-hidden="true"></i>
                        Settings
                      </span>
                      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>
                    </span>
                  </div>

                  <div className="pt-1">
                    <button type="button" onClick={() => { setProfileOpen(false); onSignOut(); }}
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 text-left flex items-center gap-2">
                      <i className="fa-solid fa-right-from-bracket w-4 text-center" aria-hidden="true"></i>
                      Sign out
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <span className="hidden items-center gap-2 sm:inline-flex">
                  <span className="text-sm text-slate-700">
                    {user.first_name} {user.last_name}
                  </span>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                    {roleLabel(user.role_code)}
                  </span>
                </span>
                <button type="button" onClick={onSignOut}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
                  Sign out
                </button>
              </>
            )}
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
              (link.href === "#" + page ? "text-counseling-active-focus" : "text-zinc-900")}
              {...(link.href === "#" + page ? { "aria-current": "page" } : {})}
              onClick={() => setMenuOpen(false)}>{link.label}</a>
          ))}
          {comingSoon.map((label) => (
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