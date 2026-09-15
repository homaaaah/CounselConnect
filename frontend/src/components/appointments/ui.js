/** Shared Tailwind class strings and label helpers for the appointments UI. */
export const inputClass = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";
export const buttonClass = "rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50";
export const secondaryClass = "rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50";
export const modeLabel = (mode) => mode === "ONLINE" ? "Online" : mode === "BOTH" ? "Online or face-to-face" : "Face-to-face";
export const dayLabel = (day) => ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day];
export const timeLabel = (value) => value.slice(0, 5);
