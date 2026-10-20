import { createContext, useContext, useState, useCallback, useMemo } from "react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback((message, { type = "info", title = "", duration = 5000 } = {}) => {
    const id = Math.random().toString(36).slice(2);
    const newToast = { id, message, type, title };
    setToasts((current) => [...current, newToast]);
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  const error = useCallback((message, opts) => notify(message, { ...opts, type: "error" }), [notify]);
  const success = useCallback((message, opts) => notify(message, { ...opts, type: "success" }), [notify]);
  const warning = useCallback((message, opts) => notify(message, { ...opts, type: "warning" }), [notify]);
  const info = useCallback((message, opts) => notify(message, { ...opts, type: "info" }), [notify]);

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

function ToastHost({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-atomic="true"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full px-4 sm:px-0"
    >
      {toasts.map((toast) => {
        const bg =
          toast.type === "error"
            ? "bg-red-900/95 text-white border-red-800"
            : toast.type === "success"
            ? "bg-emerald-900/95 text-white border-emerald-800"
            : toast.type === "warning"
            ? "bg-amber-900/95 text-white border-amber-800"
            : "bg-slate-900/95 text-white border-slate-800";
        // Errors are announced assertively; other variants politely.
        const role = toast.type === "error" ? "alert" : "status";

        return (
          <div
            key={toast.id}
            role={role}
            className={`pointer-events-auto flex items-start justify-between gap-3 rounded-xl border p-4 shadow-xl backdrop-blur-sm transition-all animate-in fade-in slide-in-from-bottom-2 ${bg}`}
          >
            <div className="space-y-1">
              {toast.title && <h3 className="text-sm font-semibold">{toast.title}</h3>}
              <p className="text-xs leading-relaxed opacity-90">{toast.message}</p>
            </div>
            <button
              type="button"
              onClick={() => onDismiss(toast.id)}
              className="shrink-0 rounded-lg p-1 text-white/70 hover:bg-white/10 hover:text-white transition-colors"
              aria-label="Dismiss notification"
            >
              <i className="fa-solid fa-xmark" aria-hidden="true"></i>
            </button>
          </div>
        );
      })}
    </div>
  );
}
