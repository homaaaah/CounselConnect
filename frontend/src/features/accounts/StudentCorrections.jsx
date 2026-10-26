import { useState } from "react";
import { request } from "../../services/apiClient";
import { useToast } from "../../components/feedback";
import { buttonClass, Comparison, dateText, EDIT_FIELDS, label, LoadState, Pagination, usePagedRecords, useRecord } from "./management";

export function RevisionForm({ detail, onSubmitted }) {
  const [fields, setFields] = useState(() => Object.fromEntries(EDIT_FIELDS.map((field) => [field, detail[`current_${field}`] ?? ""])));
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  async function submit(event) {
    event.preventDefault(); setError("");
    if (!file || !file.name.toLowerCase().endsWith(".pdf")) { setError("Attach a fresh current COR PDF."); return; }
    if (file.size > 10 * 1024 * 1024) { setError("The PDF must be 10 MB or smaller."); return; }
    const row = detail.change_request;
    const body = new FormData();
    body.append("submission_version", row.submission_version == null ? "null" : String(row.submission_version));
    body.append("file", file);
    body.append("proposed_changes", JSON.stringify({ ...fields, middle_name: String(fields.middle_name || "").trim() || null, year_level: Number(fields.year_level) }));
    setBusy(true);
    try {
      const result = await request(`/profile-change-requests/${row.change_request_id}/resubmit`, { method: "POST", body });
      setFile(null); toast.success("Correction revision submitted."); onSubmitted(result.change_request.change_request_id);
    } catch (failure) { setError(`${failure.message} Refresh the current request if its status has changed.`); }
    finally { setBusy(false); }
  }
  return <form aria-label="Resubmit correction" onSubmit={submit} className="my-4 space-y-4 rounded-lg border bg-slate-50 p-4">
    <h3 className="font-semibold">Revise and submit fresh evidence</h3><p>Change at least one field from your current registered information. Student Number, campus, program and enrollment period cannot be changed here.</p>
    <div className="grid gap-3 sm:grid-cols-2">{EDIT_FIELDS.map((field) => <label key={field}>{label(field)}
      {field === "year_level" ? <select required aria-label={label(field)} className="block w-full rounded border p-2" value={fields[field]} onChange={(event) => setFields((old) => ({ ...old, [field]: event.target.value }))}><option value="">Select year</option>{Array.from({ length: 10 }, (_, index) => index + 1).map((year) => <option key={year} value={year}>{year}</option>)}</select>
        : <input aria-label={label(field)} required={field !== "middle_name"} maxLength={field === "section" ? 50 : 100} className="block w-full rounded border p-2" value={fields[field]} onChange={(event) => setFields((old) => ({ ...old, [field]: event.target.value }))} />}
    </label>)}</div>
    <label>Fresh current COR PDF (up to 10 MB)<input aria-label="Fresh current COR PDF" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={(event) => setFile(event.target.files?.[0] || null)} className="block" /></label>
    <p className="text-sm text-slate-600">Your COR is private temporary review evidence. It is deleted after approval, return or replacement, or at its original seven-day upload deadline, whichever comes first. A later revision requires another fresh upload.</p>
    <button className={buttonClass} type="submit" disabled={busy || !file}>{busy ? "Screening and submitting…" : "Submit correction revision"}</button>
    {error && <p role="alert">{error}</p>}
  </form>;
}

export default function StudentCorrections({ user }) {
  const list = usePagedRecords("/profile-change-requests", { status: "", root_change_request_id: "" });
  const [selected, setSelected] = useState(null);
  const detail = useRecord(selected ? `/profile-change-requests/${selected}` : null);
  const data = detail.data;
  return <section className="mt-8 space-y-4 border-t pt-6" aria-label="Registration corrections">
    <h2 className="text-xl font-bold">Registration information corrections</h2>
    {user?.account_status === "ACTIVE" && !user?.is_deactivated && list.items.some((item) => item.change_request.status === "PENDING") && <p role="status">Your account is active. Your requested information changes are awaiting review.</p>}
    <p>Proposed changes remain separate from your registered information until approved.</p>
    <label>Correction status <select aria-label="My correction status" className="rounded border p-2" value={list.filters.status} onChange={(event) => { setSelected(null); list.filter("status", event.target.value); }}><option value="">All statuses</option>{["PENDING", "APPROVED", "RETURNED", "REJECTED"].map((value) => <option key={value}>{value}</option>)}</select></label>
    {list.filters.root_change_request_id && <button className={buttonClass} onClick={() => { setSelected(null); list.filter("root_change_request_id", ""); }}>Show all corrections</button>}
    <LoadState state={list} empty="No correction requests on this page." />
    <ul className="space-y-2">{list.items.map((item) => <li key={item.change_request.change_request_id} className="rounded border p-3"><button id={`my-correction-${item.change_request.change_request_id}`} className="underline" onClick={() => setSelected(item.change_request.change_request_id)}>Version {item.change_request.submission_version ?? "Unknown legacy"} · {item.change_request.status}</button> · {dateText(item.change_request.created_at)}</li>)}</ul>
    <Pagination state={list} name="My corrections" />
    {selected && <article className="space-y-4 rounded border p-4"><button className={buttonClass} onClick={() => setSelected(null)}>Close correction</button><button className={buttonClass} onClick={() => { detail.reload(); list.reload(); }}>Refresh current request</button><LoadState state={detail} />
      {data && <><h3 className="font-semibold">Request {data.change_request.change_request_id} · {data.change_request.status}</h3><Comparison detail={data} />
        {data.change_request.decision_reason && <p className="rounded border p-3">Review reason: {data.change_request.decision_reason}</p>}
        {data.change_request.status === "APPROVED" && <p>Your registered information now reflects the approved changes.</p>}
        {data.can_resubmit && <RevisionForm key={`${data.change_request.change_request_id}-${data.change_request.submission_version}`} detail={data} onSubmitted={(id) => { setSelected(id); list.reload(); }} />}
        <button className={buttonClass} onClick={() => { const row = data.change_request; setSelected(null); list.filter("status", ""); list.filter("root_change_request_id", row.root_change_request_id || row.change_request_id); }}>Browse complete correction history</button>
      </>}
    </article>}
  </section>;
}
