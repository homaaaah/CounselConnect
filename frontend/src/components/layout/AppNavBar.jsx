/**
 * AppNavBar — signed-in app shell navigation (role-aware).
 *
 * Counselor (2026-09-13): fixed left sidebar — Dashboard (#home),
 *   Users (#review, the COR verification console), Library, Appointments
 *   (#appointments), Settings. Library and Settings have no routes yet,
 *   so they render as non-navigable "coming soon" placeholders. On
 *   mobile/tablet the sidebar becomes a hamburger drawer.
 * Student / Guidance Staff: top bar as before (Home, Appointments for
 *   active students, Messages/Resources coming soon).
 *
 * Role visibility here is usability only; backend authorization
 * is authoritative (docs/USER_ROLES.md). Real session expiry is
 * handled by the 401 path in apiClient (ADR-019) — the passive
 * session-ends indicator was removed (2026-09-12).
 */

import { useEffect, useState } from "react";

// Roadmap entries: rendered as non-navigable "coming soon" placeholders
// (no href, aria-disabled) until their features ship.
const COMING_SOON = ["Messages", "Resources"];

const roleLabel = (code) =>
  code === "COUNSELOR" ? "Counselor" : code === "GUIDANCE_STAFF" ? "Guidance Staff" : "Student";

/** Counselor sidebar items; "soon" entries have no route yet. */
const COUNSELOR_NAV = [
  { label: "Dashboard", href: "#home", icon: "fa-gauge-high" },
  { label: "Users", href: "#review", icon: "fa-users" },
  { label: "Library", icon: "fa-book-open", soon: true },
  { label: "Appointments", href: "#appointments", icon: "fa-calendar" },
  { label: "Settings", icon: "fa-gear", soon: true },
];

export default function AppNavBar({ user, page, onSignOut }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  if (user.role_code === "COUNSELOR") {
    return <CounselorShell user={user} page={page} onSignOut={onSignOut} open={menuOpen} setOpen={setMenuOpen} />;
  }
  return <TopBarNav user={user} page={page} onSignOut={onSignOut} menuOpen={menuOpen} setMenuOpen={setMenuOpen} />;
}

/* ------------------------ Counselor sidebar ------------------------ */

function SidebarContent({ user, page, onSignOut, onNavigate }) {
  return <div className="flex h-full flex-col">
    <div className="border-b border-slate-200 px-5 py-4">
      <a href="#home" className="block text-base font-semibold tracking-tight text-emerald-800">CounselConnect</a>
      <span className="mt-1.5 inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
        {roleLabel(user.role_code)}
      </span>
    </div>
    <nav aria-label="Counselor navigation" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
      {COUNSELOR_NAV.map((nav) => {
        if (nav.soon) return <span key={nav.label} aria-disabled="true" title="Coming soon"
          className="flex cursor-default items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium text-slate-300">
          <i className={"fa-solid " + nav.icon + " w-4 text-center"} aria-hidden="true"></i>
          {nav.label}
          <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">soon</span>
        </span>;
        const current = nav.href === "#" + page;
        return <a key={nav.href} href={nav.href} onClick={onNavigate}
          {...(current ? { "aria-current": "page" } : {})}
          className={"flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors " +
            (current
              ? "bg-counseling-bg-tint text-counseling-active-focus"
              : "text-zinc-900 hover:bg-slate-50 hover:text-counseling-active-focus")}>
          <i className={"fa-solid " + nav.icon + " w-4 text-center"} aria-hidden="true"></i>
          {nav.label}
        </a>;
      })}
    </nav>
    <div className="border-t border-slate-200 px-5 py-4">
      <p className="text-sm text-slate-700">{user.first_name} {user.last_name}</p>
      <button type="button" onClick={onSignOut}
        className="mt-2 w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
        Sign out
      </button>
    </div>
  </div>;
}

function CounselorShell({ user, page, onSignOut, open, setOpen }) {
  return <>
    {/* Mobile/tablet top bar with the drawer toggle */}
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white lg:hidden">
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <button type="button" aria-expanded={open} aria-controls="counselor-sidebar"
          aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen(!open)}
          className="rounded-md border border-slate-300 px-2.5 py-1.5 text-slate-600 hover:bg-slate-50">
          <i className={open ? "fa-solid fa-xmark" : "fa-solid fa-bars"} aria-hidden="true"></i>
        </button>
        <a href="#home" className="text-base font-semibold tracking-tight text-emerald-800">CounselConnect</a>
        <button type="button" onClick={onSignOut}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50">
          Sign out
        </button>
      </div>
    </header>

    {/* Mobile/tablet drawer */}
    {open && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" aria-hidden="true" onClick={() => setOpen(false)}></div>}
    <aside id="counselor-sidebar" aria-label="Counselor sidebar"
      className={"fixed inset-y-0 left-0 z-50 w-64 transform border-r border-slate-200 bg-white transition-transform duration-200 lg:hidden " +
        (open ? "translate-x-0" : "-translate-x-full pointer-events-none")}>
      <SidebarContent user={user} page={page} onSignOut={onSignOut} onNavigate={() => setOpen(false)} />
    </aside>

    {/* Desktop sidebar */}
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-slate-200 bg-white lg:block">
      <SidebarContent user={user} page={page} onSignOut={onSignOut} onNavigate={() => {}} />
    </aside>
  </>;
}

/* ---------------- Top bar (Student / Guidance Staff) ---------------- */

function TopBarNav({ user, page, onSignOut, menuOpen, setMenuOpen }) {
  const links = [{ label: "Home", href: "#home" }];
  const activeStudent = user.role_code === "STUDENT" && user.account_status === "ACTIVE";
  if (activeStudent) links.push({ label: "Appointments", href: "#appointments" });
  const showComingSoon = user.role_code === "STUDENT";

  const linkClass = (href) => {
    const current = href === "#" + page;
    return "px-1 py-4 text-sm font-medium transition-colors " +
      (current
        ? "border-b-2 border-counseling-active-focus text-zinc-900"
        : "border-b-2 border-transparent text-zinc-900 hover:text-counseling-active-focus");
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
              (link.href === "#" + page ? "text-counseling-active-focus" : "text-zinc-900")}
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
