/**
 * AppNavBar — signed-in app shell navigation (role-aware).
 *
 * All signed-in roles share one top-bar header. Only the links and the
 * "coming soon" entries differ by role:
 *   - Counselor: Dashboard (#home), Appointments (#appointments), Schedule
 *     (#schedule), History (#history); Sessions has no route yet, so it
 *     renders as a non-navigable "coming soon" placeholder. The Users
 *     directory is Superadmin-only for now (deferred counselor feature).
 *     Active link is green with a thin underline, and the right side shows a
 *     notification bell plus a text-only identity block (Navbar UI Spec).
 *   - Superadmin: Users and Registration Corrections.
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

// ponytail: no notifications API yet, so the badge only shows when a real
// count is supplied; add the source when the feature ships.
function NotificationBell({ count = 0, onOpen }) {
  return (
    <button type="button" onClick={onOpen}
      aria-label={count > 0 ? `Notifications, ${count} unread` : "Notifications"}
      className="relative rounded-full p-2 text-[#207524] hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[#207524]">
      <i className="fa-solid fa-bell text-lg" aria-hidden="true"></i>
      {count > 0 && (
        <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#E44D53] px-1 text-[10px] font-semibold text-white">
          {count}
        </span>
      )}
    </button>
  );
}

/**
 * Role-based navigation for the shared top bar, as an ordered item list.
 * Items with an `href` navigate; items flagged `soon` render as
 * non-navigable placeholders until their features ship.
 */
function roleNav(user) {
  if (user.role_code === "COUNSELOR") {
    return [
      { label: "Dashboard", href: "#home" },
      { label: "Appointments", href: "#appointments" },
      // Non-navigable placeholder: visible but not clickable, no "soon" tag.
      { label: "Sessions", soon: true, badge: false },
      { label: "Schedule", href: "#schedule" },
      { label: "History", href: "#history" },
    ];
  }
  if (user.role_code === "SUPERADMIN") {
    return [{ label: "Users", href: "#users" }, { label: "Registration Corrections", href: "#corrections" }, { label: "Account Recovery", href: "#student-directory" }];
  }
  if (user.role_code === "GUIDANCE_STAFF") {
    return [{ label: "Home", href: "#home" }];
  }
  const active = user.account_status === "ACTIVE";
  return (active
    ? [{ label: "Home", href: "#home" }, { label: "Appointments", href: "#appointments" }]
    : [{ label: "Home", href: "#home" }])
    .concat([{ label: "History", soon: true }, { label: "Session", soon: true }]);
}

export default function AppNavBar({ user, page, onSignOut, notificationCount = 0, onNotificationsOpen }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return <TopBarNav user={user} page={page} onSignOut={onSignOut} menuOpen={menuOpen} setMenuOpen={setMenuOpen}
    notificationCount={notificationCount} onNotificationsOpen={onNotificationsOpen} />;
}

/* ---------------- Top bar (all signed-in roles) ---------------- */

function TopBarNav({ user, page, onSignOut, menuOpen, setMenuOpen, notificationCount, onNotificationsOpen }) {
  const [profileOpen, setProfileOpen] = useState(false);
  const items = roleNav(user);
  const isStudent = user.role_code === "STUDENT";
  const isCounselor = user.role_code === "COUNSELOR";
  const isSuperadmin = user.role_code === "SUPERADMIN";
  // Superadmin shares the counselor's green active-link treatment.
  const isGreen = isCounselor || user.role_code === "SUPERADMIN";

  useEffect(() => {
    if (!profileOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setProfileOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [profileOpen]);

  const isCurrent = href => href === "#" + page || (isSuperadmin && page === "home" && href === "#users");
  const linkClass = (href) => {
    const current = isCurrent(href);
    // Counselor reference state: green text with a thin green underline.
    const active = isGreen
      ? "border-b-2 border-[#207524] text-[#207524]"
      : "border-b-2 border-counseling-active-focus text-zinc-900";
    const hover = isGreen ? "hover:text-[#207524]" : "hover:text-counseling-active-focus";
    return "px-1 py-4 text-sm font-medium transition-colors " +
      (current
        ? active
        : "border-b-2 border-transparent text-zinc-900 " + hover);
  };

  const bannerText = user.role_code !== "STUDENT" || user.account_status === "ACTIVE" ? null
    : user.account_status === "PENDING_VERIFICATION"
      ? "Verification pending — confirm your COR details to unlock scheduling."
      : user.account_status === "VERIFICATION_EXPIRED"
        ? "Enrollment expired — re-verify your COR to restore scheduling."
        : "Scheduling is locked for your account status.";

  return (
    <>
      <header className={"sticky top-0 z-40 border-b border-slate-200 bg-white" + (isSuperadmin ? " superadmin-nav" : "")}>
        <nav aria-label="App navigation" className="mx-auto flex max-w-6xl items-center gap-4 px-4 sm:px-6">
          <a href="#home" className={"flex items-center gap-2 py-2 text-base font-semibold tracking-tight text-slate-700" + (isSuperadmin ? " superadmin-brand" : "")}>
            {/* Same brand mark as the login/register modal header (modal.css .brand-logo). */}
            <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 border-[#1C6B1B] bg-[#e8f5e9] text-xs text-[#1C6B1B]">
              {isSuperadmin ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11ZM9 12l2 2 4-4" /></svg> : <i className="fa-solid fa-hands-holding-child"></i>}
            </span>
            CounselConnect
          </a>
          <div className={"hidden items-center gap-5 " + (isSuperadmin ? "lg:flex" : "md:flex")}>
            {items.map((link) => link.href ? (
              <a key={link.href} href={link.href} className={linkClass(link.href)}
                {...(isCurrent(link.href) ? { "aria-current": "page" } : {})}
                onClick={() => setMenuOpen(false)}>{link.label}</a>
            ) : (
              <span key={link.label} aria-disabled="true" title="Coming soon"
                className="inline-flex cursor-default items-center gap-1 border-b-2 border-transparent px-1 py-4 text-sm text-slate-300">
                {link.label}
                {link.badge !== false && <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>}
              </span>
            ))}
            {isStudent && (
              <a href="#registration" className={linkClass("#registration")}
                {...(page === "registration" ? { "aria-current": "page" } : {})}>
                {user.account_status === "ACTIVE" ? "Registration" : "Verify enrollment"}
              </a>
            )}
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
            ) : isCounselor ? (
              <>
                <NotificationBell count={notificationCount} onOpen={onNotificationsOpen} />
                <span className="hidden text-right leading-tight sm:block">
                  <span className="block text-sm font-semibold text-slate-700">{user.first_name} {user.last_name}</span>
                  <span className="block text-xs text-[#7B8493]">{roleLabel(user.role_code)}</span>
                </span>
                <button type="button" onClick={onSignOut}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
                  Sign out
                </button>
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
            <button type="button" className={"flex h-11 w-11 shrink-0 items-center justify-center rounded-md " + (isSuperadmin ? "lg:hidden" : "md:hidden")} aria-expanded={menuOpen} aria-controls="app-nav-links"
              aria-label={menuOpen ? "Close menu" : "Open menu"} onClick={() => setMenuOpen(!menuOpen)}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d={menuOpen ? "M6 6l12 12M6 18L18 6" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </nav>
        <div id="app-nav-links" hidden={!menuOpen}
          className={"border-t border-slate-200 bg-white px-4 pb-3 " + (isSuperadmin ? "lg:hidden" : "md:hidden")}>
          {items.map((link) => link.href ? (
            <a key={link.href} href={link.href} className={"block py-2.5 text-sm font-medium " +
              (isCurrent(link.href)
                ? (isGreen ? "text-[#207524]" : "text-counseling-active-focus")
                : "text-zinc-900 " + (isGreen ? "hover:text-[#207524]" : "hover:text-counseling-active-focus"))}
              {...(isCurrent(link.href) ? { "aria-current": "page" } : {})}
              onClick={() => setMenuOpen(false)}>{link.label}</a>
          ) : (
            <span key={link.label} aria-disabled="true" title="Coming soon"
              className="flex items-center gap-1 py-2.5 text-sm text-slate-300">
              {link.label}
              {link.badge !== false && <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>}
            </span>
          ))}
          {user.role_code === "STUDENT" && (
            <a href="#registration" onClick={() => setMenuOpen(false)}
              className={"block py-2.5 text-sm font-medium " +
                (page === "registration" ? "text-counseling-active-focus" : "text-zinc-900")}
              {...(page === "registration" ? { "aria-current": "page" } : {})}>
              {user.account_status === "ACTIVE" ? "Registration" : "Verify enrollment"}
            </a>
          )}
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
