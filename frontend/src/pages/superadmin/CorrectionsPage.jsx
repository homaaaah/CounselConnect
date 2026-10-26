import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";
import { useToast } from "../../components/feedback";
import { buttonClass, primaryClass, Comparison, dateText, LoadState, Pagination, PrivateCorPreview, usePagedRecords, useRecord } from "../../features/accounts/management";

const STATUS_STYLES = {
  PENDING: "bg-amber-100 text-amber-800",
  APPROVED: "bg-emerald-100 text-emerald-800",
  RETURNED: "bg-blue-100 text-blue-800",
  REJECTED: "bg-red-100 text-red-800",
};

function StatusBadge({ value }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <span className={"inline-block rounded-full px-2 py-0.5 text-xs font-medium " + (STATUS_STYLES[value] ?? "bg-slate-100 text-slate-700")}>
      {String(value).replaceAll("_", " ")}
    </span>
  );
}

export default function CorrectionsPage() {
  const list = usePagedRecords("/profile-change-requests", { status: "PENDING", root_change_request_id: "" });
  const [selected, setSelected] = useState(null);
  const detail = useRecord(selected ? `/profile-change-requests/${selected}` : null);
  const [decision, setDecision] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [, updateClock] = useState(0);
  const toast = useToast();
  function select(id) { setSelected(id); setDecision(null); setReason(""); setError(""); }
  function filter(key, value) { select(null); list.filter(key, value); }
  async function decide() {
    const action = decision;
    setBusy(true); setError("");
    try {
      await request(`/profile-change-requests/${action.id}/${action.kind}`, { method: "POST", body: JSON.stringify({ submission_version: action.version, ...(action.kind === "return" ? { reason: reason.trim() } : {}) }) });
      setDecision(null); setReason(""); list.reload(); detail.reload();
      toast.success(action.kind === "approve" ? "Corrections approved." : "Correction request returned.");
    } catch (failure) {
      setError(`${failure.message} Reload the current request before another decision.`);
      setDecision(null); detail.reload(); list.reload();
    } finally { setBusy(false); }
  }
  const data = detail.data;
  const row = data?.change_request;
  const deadline = data?.evidence?.expires_at ? new Date(data.evidence.expires_at).getTime() : NaN;
  useEffect(() => {
    if (!Number.isFinite(deadline) || deadline <= Date.now()) return;
    const timer = setTimeout(() => updateClock((old) => old + 1), deadline - Date.now() + 1);
    return () => clearTimeout(timer);
  }, [deadline]);
  const canApprove = row?.status === "PENDING" && Number.isInteger(row.submission_version) && data?.evidence?.availability === "AVAILABLE" && Number.isFinite(deadline) && deadline > Date.now();
  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#207524]">Registration Corrections</h1>
          <p className="mt-1 text-sm text-slate-600">Review proposed information against the submitted COR. Approval records consistency with this document, not University authenticity.</p>
        </div>
      </header>

      <section className="space-y-4 rounded-2xl border border-[#E9EDF1] bg-white p-6">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-700">Status
            <select aria-label="Correction status" className="form-select mt-1" value={list.filters.status} onChange={(event) => filter("status", event.target.value)}>
              <option value="">All statuses</option>
              {["PENDING", "APPROVED", "RETURNED", "REJECTED"].map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          {list.filters.root_change_request_id && <button className={buttonClass} onClick={() => filter("root_change_request_id", "")}>Show all request histories</button>}
        </div>
        <LoadState state={list} />
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Correction requests</caption>
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
              <tr>{["Student", "Status", "Version", "Changed fields", "Submitted", "Review"].map((title) => <th key={title} className="px-4 py-3">{title}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100">{list.items.map((item) => <tr key={item.change_request.change_request_id} className="align-top">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-800">{item.student.first_name} {item.student.last_name}</div>
                <div className="text-xs text-slate-600">{item.student.email}</div>
              </td>
              <td className="px-4 py-3"><StatusBadge value={item.change_request.status} /></td>
              <td className="px-4 py-3 text-slate-700">{item.change_request.submission_version ?? "Unknown legacy"}</td>
              <td className="px-4 py-3 text-slate-700">{item.changed_fields == null ? "Comparison unavailable" : item.changed_fields.length ? item.changed_fields.join(", ") : "No changes"}</td>
              <td className="px-4 py-3 text-slate-600">{dateText(item.change_request.created_at)}</td>
              <td className="px-4 py-3 text-right"><button className={buttonClass} id={`review-open-${item.change_request.change_request_id}`} onClick={() => select(item.change_request.change_request_id)}>Review</button></td>
            </tr>)}</tbody>
          </table>
        </div>
        <Pagination state={list} name="Corrections" />
      </section>
    </div>

    {selected && <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Correction review"
      onClick={(event) => { if (event.target === event.currentTarget) select(null); }}>
      <div className="signup-card" style={{ maxWidth: "900px" }}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900">{data ? `${data.student.first_name} ${data.student.last_name}` : "Correction review"}</h2>
              {row && <StatusBadge value={row.status} />}
            </div>
            <p className="text-sm text-slate-600">{row ? `Request ${row.change_request_id} · Version ${row.submission_version ?? "Unknown legacy"}` : "Loading request…"}</p>
          </div>
          <button type="button" className="modal-close" onClick={() => select(null)} aria-label="Close">
            <i className="fa-solid fa-xmark" aria-hidden="true"></i>
          </button>
        </div>
        <LoadState state={detail} />
        {data && <div className="space-y-4">
          <p className="text-sm text-slate-600">{data.student.email}</p>
          <Comparison detail={data} reviewer />
          {!busy && <PrivateCorPreview key={`${row.change_request_id}-${row.status}`} id={row.change_request_id} evidence={data.evidence} />}
          {row.decision_reason && <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Return reason: {row.decision_reason}</p>}
          <div className="flex flex-wrap gap-3">
            <button id={`review-approve-${row.change_request_id}`} className={primaryClass} disabled={busy || !canApprove} onClick={() => setDecision({ id: row.change_request_id, version: row.submission_version, kind: "approve" })}>Approve whole request</button>
            <button id={`review-return-${row.change_request_id}`} className={buttonClass} disabled={busy || row.status !== "PENDING"} onClick={() => setDecision({ id: row.change_request_id, version: row.submission_version, kind: "return" })}>Return whole request</button>
          </div>
          {row.submission_version == null && <p className="text-sm text-slate-500">Legacy context is unknown. This version can be returned for fresh evidence, but cannot be approved.</p>}
          <div>
            <h3 className="text-sm font-bold text-slate-700">Recent version history</h3>
            <ul className="mt-2 space-y-1 text-sm">{data.history.map((item) => <li key={item.change_request_id}>
              <button className="linklike" onClick={() => select(item.change_request_id)}>Version {item.submission_version ?? "Unknown legacy"}: {item.status}</button>
              <span className="text-slate-500"> · {dateText(item.created_at)}</span>
            </li>)}</ul>
          </div>
          <button className={buttonClass} onClick={() => { const root = row.root_change_request_id || row.change_request_id; select(null); list.filter("status", ""); list.filter("root_change_request_id", root); }}>Browse complete history</button>
        </div>}
        {decision && decision.id === selected && <fieldset className="mt-4 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4"><legend className="font-semibold text-slate-800">Confirm {decision.kind === "approve" ? "approval" : "return"} of request {decision.id}, version {decision.version ?? "Unknown legacy"}</legend>
          {decision.kind === "return" ? <label className="block text-sm font-semibold text-slate-700">What needs correction?<textarea aria-label="Return reason" maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} className="form-input mt-1" /></label> : <p className="text-sm text-slate-600">Apply all proposed changes shown for this version after checking the submitted COR.</p>}
          <div className="flex gap-2"><button className={buttonClass} disabled={busy} onClick={() => setDecision(null)}>Cancel</button><button id="confirm-correction-decision" className={primaryClass} disabled={busy || (decision.kind === "return" ? !reason.trim() : !canApprove)} onClick={decide}>{busy ? "Saving…" : "Confirm decision"}</button></div>
        </fieldset>}
        {error && <p role="alert" className="form-message error mt-4">{error}</p>}
      </div>
    </div>}
  </main>;
}