import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";

export const EDIT_FIELDS = ["first_name", "middle_name", "last_name", "year_level", "section"];
export const label = (field) => field.replaceAll("_", " ").replace(/^./, (value) => value.toUpperCase());
export const valueText = (value) => value === null || value === undefined || value === "" ? "None / unavailable" : String(value);
export const dateText = (value) => value ? new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila", dateStyle: "medium", timeStyle: "short",
}).format(new Date(value)) : "Unavailable";
export const buttonClass = "rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50";
export const primaryClass = "rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50";

export function usePagedRecords(path, initialFilters = {}) {
  const [query, setQuery] = useState({ filters: initialFilters, page: 1 });
  const [revision, setRevision] = useState(0);
  const params = new URLSearchParams({ page: query.page, page_size: 20 });
  Object.entries(query.filters).forEach(([key, value]) => { if (value !== "" && value != null) params.set(key, value); });
  const url = `${path}?${params}`;
  const [state, setState] = useState({ key: null, items: [], total: 0, loading: true, error: "" });
  useEffect(() => {
    let active = true;
    setState({ key: url, items: [], total: 0, loading: true, error: "" });
    request(url, { cache: "no-store" }).then((data) => {
      if (!Array.isArray(data?.items) || !Number.isInteger(data.total) || data.total < 0) throw new Error("Could not read this result page. Please retry.");
      const lastPage = Math.max(1, Math.ceil(data.total / 20));
      if (active && query.page > lastPage) { setQuery((old) => old === query ? { ...old, page: lastPage } : old); return; }
      if (active) setState({ key: url, items: data.items, total: data.total, loading: false, error: "" });
    }).catch((error) => { if (active) setState({ key: url, items: [], total: 0, loading: false, error: error.message }); });
    return () => { active = false; };
  }, [url, revision]);
  const filter = (key, value) => setQuery((old) => ({ page: 1, filters: { ...old.filters, [key]: value } }));
  const reload = useCallback(() => setRevision((old) => old + 1), []);
  return { ...(state.key === url ? state : { items: [], total: 0, loading: true, error: "" }), ...query,
    filter, setPage: (page) => setQuery((old) => ({ ...old, page })), reload };
}

export function useRecord(path) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ key: null, data: null, loading: false, error: "" });
  useEffect(() => {
    if (!path) return;
    let active = true;
    setState({ key: path, data: null, loading: true, error: "" });
    request(path, { cache: "no-store" }).then((data) => {
      if (active) setState({ key: path, data, loading: false, error: "" });
    }).catch((error) => { if (active) setState({ key: path, data: null, loading: false, error: error.message }); });
    return () => { active = false; };
  }, [path, revision]);
  return { ...(state.key === path ? state : { data: null, loading: Boolean(path), error: "" }),
    reload: useCallback(() => setRevision((old) => old + 1), []) };
}

export function LoadState({ state, empty = "No records on this page." }) {
  if (state.loading) return <p role="status" className="text-sm text-slate-500">Loading…</p>;
  if (state.error) return <div role="alert" className="form-message error my-4">{state.error} <button className="linklike" onClick={state.reload}>Retry</button></div>;
  return state.items?.length === 0 ? <p className="text-sm text-slate-500">{empty}</p> : null;
}

export function Pagination({ state, name = "Records" }) {
  const pages = Math.max(1, Math.ceil(state.total / 20));
  return <nav aria-label={`${name} pages`} className="management-pagination my-4 flex flex-wrap items-center gap-3">
    <button className={buttonClass} disabled={state.loading || state.page <= 1} onClick={() => state.setPage(state.page - 1)}>Previous</button>
    <span className="text-sm text-slate-600">{state.loading ? `Loading page ${state.page}…` : state.error ? `Page ${state.page} unavailable` : `Page ${state.page} of ${pages} · ${state.total} records`}</span>
    <button className={buttonClass} disabled={state.loading || Boolean(state.error) || state.page >= pages} onClick={() => state.setPage(state.page + 1)}>Next</button>
    <button className={buttonClass} disabled={state.loading} onClick={state.reload}>Refresh</button>
  </nav>;
}

export function Comparison({ detail, reviewer = false }) {
  const row = detail.change_request;
  const baseline = detail.registered_values_at_submission;
  const current = reviewer ? detail.current_registered_values : Object.fromEntries(EDIT_FIELDS.map((field) => [field, detail[`current_${field}`]]));
  const show = (values, field) => values == null || values[field] === undefined ? "Unavailable"
    : values[field] === null ? (field === "middle_name" ? "None" : "Unavailable") : valueText(values[field]);
  return <div className="overflow-x-auto">
    {detail.changed_fields === null && <p className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Historical comparison unavailable. Stored proposals are shown without an inferred difference.</p>}
    <table className="comparison-table min-w-full divide-y divide-slate-200 text-sm"><caption className="text-left text-sm font-semibold text-slate-700">Registration comparison</caption>
      <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600"><tr>{["Field", ...(reviewer ? ["COR extraction"] : []), "Registered at submission", "Current registered", "Proposed", "Difference"].map((title) => <th key={title} className="px-4 py-3">{title}</th>)}</tr></thead>
      <tbody className="divide-y divide-slate-100">{EDIT_FIELDS.map((field) => <tr key={field} className={detail.changed_fields?.includes(field) ? "comparison-changed" : undefined}>
        <th className="px-4 py-3 font-medium text-slate-700">{label(field)}</th>
        {reviewer && <td className="px-4 py-3">{show(detail.extracted_values, field)}</td>}
        <td className="px-4 py-3">{show(baseline, field)}</td><td className="px-4 py-3">{show(current, field)}</td>
        <td className="px-4 py-3">{show({ [field]: row[`requested_${field}`] }, field)}</td>
        <td className="px-4 py-3">{detail.changed_fields === null ? "Unknown" : detail.changed_fields?.includes(field) ? "Changed" : "Unchanged"}</td>
      </tr>)}</tbody></table>
    {reviewer && <table className="comparison-table my-4 min-w-full divide-y divide-slate-200 text-sm"><caption className="text-left text-sm font-semibold text-slate-700">Read-only enrollment context</caption><thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600"><tr>{["Field", "COR extraction", "Registered at submission", "Current registered"].map((title) => <th key={title} className="px-4 py-3">{title}</th>)}</tr></thead><tbody className="divide-y divide-slate-100">{["student_number", "campus_id", "program_id", "academic_period", "valid_until"].map((field) =>
      <tr key={field}><th className="px-4 py-3 font-medium text-slate-700">{label(field)}</th><td className="px-4 py-3">{show(detail.extracted_values, field)}</td><td className="px-4 py-3">{show(baseline, field)}</td><td className="px-4 py-3">{show(current, field)}</td></tr>)}</tbody></table>}
  </div>;
}

export function PrivateCorPreview({ id, evidence, polished = false }) {
  const [url, setUrl] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const live = useRef(0);
  const ownedUrl = useRef(null);
  const deadline = evidence?.expires_at ? new Date(evidence.expires_at).getTime() : NaN;
  const release = useCallback(() => {
    live.current++;
    if (ownedUrl.current) URL.revokeObjectURL(ownedUrl.current);
    ownedUrl.current = null;
    setUrl(null);
  }, []);
  useEffect(() => {
    const timer = Number.isFinite(deadline) ? setTimeout(() => { release(); setError("Evidence expired. Refresh the request."); }, Math.max(0, deadline - Date.now())) : null;
    return () => { if (timer) clearTimeout(timer); release(); };
  }, [id, deadline, release]);
  async function preview() {
    release();
    const generation = live.current;
    setBusy(true); setError("");
    try {
      const blob = await request(`/profile-change-requests/${id}/cor`, { responseType: "blob", cache: "no-store" });
      if (generation !== live.current) return;
      if (Date.now() >= deadline) throw new Error("Evidence expired. Refresh the request.");
      ownedUrl.current = URL.createObjectURL(blob);
      setUrl(ownedUrl.current);
    } catch (failure) { if (generation === live.current) setError(failure.message); }
    finally { if (generation === live.current) setBusy(false); }
  }
  return <section className="management-preview my-4 space-y-3 rounded-xl border border-slate-200 bg-white p-4"><h3 className="management-section-title">Submitted COR</h3><p className="text-sm text-slate-600">Evidence: {evidence?.availability || "UNAVAILABLE"} · Deadline: {dateText(evidence?.expires_at)}</p>
    <button className={polished ? "management-button" : buttonClass} disabled={busy || evidence?.availability !== "AVAILABLE" || !Number.isFinite(deadline) || Date.now() >= deadline} onClick={preview}>{busy ? "Loading preview…" : "Preview current COR"}</button>
    {error && <p role="alert" className="form-message error">{error}</p>}
    {url && <><button className={polished ? "management-button" : buttonClass} onClick={release}>Close preview</button><iframe title="Current correction COR" src={url} className="h-96 w-full rounded-lg border" /></>}
  </section>;
}
