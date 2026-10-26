import { concernLabel } from "./concerns.js";

export default function ConcernSummary({ categories, details, className = "" }) {
  if (!Array.isArray(categories) || categories.length === 0) return null;
  const [priority, ...additional] = categories;
  return <section aria-label="Student-stated concern" className={"space-y-1 " + className}>
    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Student-stated concern</p>
    <p className="text-sm text-slate-800"><span className="font-semibold">Priority:</span> {concernLabel(priority)}</p>
    {additional.length > 0 && <p className="text-sm text-slate-700"><span className="font-medium">Also selected:</span> {additional.map(concernLabel).join(", ")}</p>}
    {details && <p className="whitespace-pre-wrap text-sm text-slate-600"><span className="font-medium">Details:</span> {details}</p>}
  </section>;
}
