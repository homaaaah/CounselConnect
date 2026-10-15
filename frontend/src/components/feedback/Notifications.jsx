/**
 * Notifications — app-wide visual alerts (toasts).
 *
 * <ToastProvider> mounts a fixed toast host; any component (or the global API
 * error observer) can raise a visual notification with useToast(). Errors are
 * announced to assistive tech (role="alert"); other variants use role="status".
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

const ToastContext = createContext(null);

const VARIANTS = {
  error: {
    role: "alert",
    box: "border-red-300 bg-red-50 text-red-900",
    icon: "fa-circle-exclamation",
    iconColor: "text-red-600",
    bar: "bg-red-500",
  },
  success: {
    role: "status",
    box: "border-emerald-300 bg-emerald-50 text-emerald-900",
    icon: "fa-circle-check",
    iconColor: "text-emerald-600",
    bar: "bg-emerald-500",
  },
  warning: {
    role: "status",
    box: "border-amber-300 bg-amber-50 text-amber-900",
    icon: "fa-triangle-exclamation",
    iconColor: "text-amber-600",
    bar: "bg-amber-500",
  },
  info: {
    role: "status",
    box: "border-blue-300 bg-blue-50 text-blue-900",
    icon: "fa-circle-info",
    iconColor: "text-blue-600",
    bar: "bg-blue-500",
  },
};

let toastSeq = 0;

function ToastHost({ toasts, onDismiss }) {
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed inset-x-4 top-4 z-[100] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-4 sm:items-end"
    >
      {toasts.map((toast) => {
        const variant = VARIANTS[toast.variant] ?? VARIANTS.info;
        return (
          <div
            key={toast.id}
            role={variant.role}
            className={
              "pointer-events-auto w-full max-w-md overflow-hidden rounded-xl border shadow-lg " +
              variant.box
            }
          >
            <div className="flex items-start gap-3 p-3">
              <i className={`fa-solid ${variant.icon} mt-0.5 ${variant.iconColor}`} aria-hidden="true"></i>
              <div className="min-w-0 flex-1">
                {toast.title && <p className="text-sm font-semibold">{toast.title}</p>}
                <p className="text-sm break-words">{toast.message}</p>
              </div>
              <button
                type="button"
                onClick={() => onDismiss(toast.id)}
                aria-label="Dismiss notification"
                className="rounded p-1 text-current opacity-70 hover:opacity-100"
              >
                <i className="fa-solid fa-xmark" aria-hidden="true"></i>
              </button>
            </div>
            <div className={`h-0.5 w-full ${variant.bar}`} />
          </div>
        );
      })}
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback((message, options = {}) => {
    if (!message) return null;
    const id = ++toastSeq;
    const variant = VARIANTS[options.variant] ? options.variant : "info";
    const duration = options.duration ?? 6500;
    setToasts((current) => [
      ...current.slice(-3),
      { id, message: String(message), variant, title: options.title, duration },
    ]);
    if (duration > 0) {
      timers.current.set(id, setTimeout(() => dismiss(id), duration));
    }
    return id;
  }, [dismiss]);

  useEffect(() => () => {
    for (const timer of timers.current.values()) clearTimeout(timer);
    timers.current.clear();
  }, []);

  const error = useCallback((message, options) => notify(message, { ...options, variant: "error" }), [notify]);
  const success = useCallback((message, options) => notify(message, { ...options, variant: "success" }), [notify]);
  const warning = useCallback((message, options) => notify(message, { ...options, variant: "warning" }), [notify]);
  const info = useCallback((message, options) => notify(message, { ...options, variant: "info" }), [notify]);

  const api = useMemo(() => ({
    notify,
    error,
    success,
    warning,
    info,
    dismiss,
    toasts,
  }), [notify, error, success, warning, info, dismiss, toasts]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastHost toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within ToastProvider");
  return context;
}
