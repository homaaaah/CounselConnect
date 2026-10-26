import { useEffect, useRef } from "react";
import "./superadmin.css";

const paths = {
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  review: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8ZM14 2v6h6M8 13h8M8 17h5",
  recovery: "M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2",
  shield: "M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11ZM9 12l2 2 4-4",
  close: "M6 6l12 12M6 18 18 6",
};

export function ManagementIcon({ name = "users", size = 22 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.users} /></svg>;
}

export function ManagementHeader({ title, description, icon, children }) {
  return <header className="management-header">
    <div className="management-heading"><span className="management-heading-icon"><ManagementIcon name={icon} size={26} /></span><div>
      <p className="management-eyebrow">Account operations</p><h1>{title}</h1><p className="management-description">{description}</p>
    </div></div>
    {children && <div className="management-header-actions">{children}</div>}
  </header>;
}

export function ManagementPage({ title, description, icon, actions, children }) {
  return <main className="superadmin-page"><div className="management-workspace">
    <ManagementHeader title={title} description={description} icon={icon}>{actions}</ManagementHeader>
    {children}
  </div></main>;
}

export function ManagementPanel({ title, description, actions, children, className = "" }) {
  return <section className={`management-panel ${className}`}>
    {(title || actions) && <header className="management-panel-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{actions && <div>{actions}</div>}</header>}
    {children}
  </section>;
}

export function ManagementBadge({ value, tone }) {
  if (value == null || value === "") return <span className="management-muted">Unavailable</span>;
  const inferred = ["ACTIVE", "APPROVED", "PASSED", "Enabled"].includes(value) ? "success"
    : ["PENDING", "PENDING_VERIFICATION", "AWAITING_CONFIRMATION", "RETURNED"].includes(value) ? "warning"
    : ["FAILED", "Deactivated"].includes(value) ? "danger" : "neutral";
  return <span className={`management-badge management-badge--${tone || inferred}`}>{String(value).replaceAll("_", " ")}</span>;
}

export function ManagementDetail({ label, children }) {
  return <div className="management-detail"><dt>{label}</dt><dd>{children}</dd></div>;
}

export function ManagementDialog({ label, title, subtitle, onClose, children, wide = false, closeDisabled = false }) {
  const container = useRef(null);
  const close = useRef(onClose);
  close.current = closeDisabled ? () => {} : onClose;
  useEffect(() => {
    if (typeof document === "undefined" || !container.current) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => [...container.current.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]')].filter(node => node.getClientRects().length > 0);
    focusable()[0]?.focus();
    function onKey(event) {
      if (event.key === "Escape") { event.preventDefault(); close.current(); }
      if (event.key !== "Tab") return;
      const controls = focusable();
      const first = controls[0], last = controls[controls.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || !container.current.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !container.current.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus();
    };
  }, []);
  return <div className="management-overlay" role="dialog" aria-modal="true" aria-label={label} onClick={event => { if (!closeDisabled && event.target === event.currentTarget) onClose(); }}>
    <section ref={container} className={`superadmin-dialog${wide ? " superadmin-dialog--wide" : ""}`}>
      <header className="management-dialog-header"><div><p className="management-eyebrow">{label}</p><h2>{title}</h2>{subtitle && <p className="management-description">{subtitle}</p>}</div>
        <button type="button" className="management-close" disabled={closeDisabled} onClick={onClose} aria-label={`Close ${label.toLowerCase()}`}><ManagementIcon name="close" /></button>
      </header>
      <div className="management-dialog-body">{children}</div>
    </section>
  </div>;
}
