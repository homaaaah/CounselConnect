import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";
import { useToast } from "../../components/feedback";
import { Comparison, dateText, LoadState, Pagination, PrivateCorPreview, usePagedRecords, useRecord } from "../../features/accounts/management";

import { ManagementPage, ManagementPanel, ManagementDialog, ManagementBadge } from "../../features/accounts/SuperadminLayout";

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
  return <ManagementPage title="Registration Corrections" icon="review" description="Review proposed changes against the submitted COR. Approval records document consistency, not University authenticity.">
    <ManagementPanel>
      <div className="management-filters management-filters--compact"><label className="management-field">Request status
        <select aria-label="Correction status" value={list.filters.status} onChange={event => filter("status", event.target.value)}><option value="">All statuses</option>{["PENDING", "APPROVED", "RETURNED", "REJECTED"].map(value => <option key={value}>{value}</option>)}</select>
      </label><div className="management-actions">{list.filters.root_change_request_id && <button className="management-button" onClick={() => filter("root_change_request_id", "")}>Show all request histories</button>}</div></div>
    </ManagementPanel>
    <ManagementPanel title={list.filters.root_change_request_id ? "Correction history" : "Correction requests"} description="Each review applies to the complete request and its displayed version."
      actions={!list.loading && !list.error && <span className="management-count"><strong>{list.total}</strong> request{list.total === 1 ? "" : "s"}</span>}>
      {(list.loading || list.error || list.items.length === 0) && <div className="management-state"><LoadState state={list} empty="No correction requests match these filters." /></div>}
      <div className="management-table-scroll"><table className="management-table"><caption className="sr-only">Correction requests</caption>
        <thead><tr>{["Student", "Status", "Version", "Changed fields", "Submitted", "Review"].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
        <tbody>{list.items.map(item => <tr key={item.change_request.change_request_id}>
          <td><div className="management-name">{item.student.first_name} {item.student.last_name}</div><span className="management-subtext">{item.student.email}</span></td>
          <td><ManagementBadge value={item.change_request.status} /></td>
          <td>{item.change_request.submission_version ?? "Unknown legacy"}</td>
          <td>{item.changed_fields == null ? "Comparison unavailable" : item.changed_fields.length ? item.changed_fields.map(field => field.replaceAll("_", " ")).join(", ") : "No changes"}</td>
          <td>{dateText(item.change_request.created_at)}</td>
          <td><button className="management-button" id={"review-open-" + item.change_request.change_request_id} onClick={() => select(item.change_request.change_request_id)}>Review</button></td>
        </tr>)}</tbody>
      </table></div>
      <Pagination state={list} name="Corrections" />
    </ManagementPanel>

    {selected && <ManagementDialog wide label="Correction review" title={data ? data.student.first_name + " " + data.student.last_name : "Review request"}
      subtitle={row ? "Request " + row.change_request_id + " · Version " + (row.submission_version ?? "Unknown legacy") : "Loading request…"} onClose={() => select(null)}>
      <LoadState state={detail} />
      {data && <>
        <div className="management-actions"><ManagementBadge value={row.status} /><span className="management-muted">{data.student.email}</span></div>
        <Comparison detail={data} reviewer />
        {!busy && <PrivateCorPreview polished key={row.change_request_id + "-" + row.status} id={row.change_request_id} evidence={data.evidence} />}
        {row.decision_reason && <p className="management-notice management-notice--warning">Return reason: {row.decision_reason}</p>}
        <section className="management-action-section"><h3 className="management-section-title">Review decision</h3>
          <p className="management-description" style={{ marginBottom: 14 }}>Approve all proposed changes for this version, or return the request with clear instructions for the Student.</p>
          <div className="management-actions"><button id={"review-approve-" + row.change_request_id} className="management-button management-button--primary" disabled={busy || !canApprove} onClick={() => setDecision({ id: row.change_request_id, version: row.submission_version, kind: "approve" })}>Approve whole request</button>
            <button id={"review-return-" + row.change_request_id} className="management-button" disabled={busy || row.status !== "PENDING"} onClick={() => setDecision({ id: row.change_request_id, version: row.submission_version, kind: "return" })}>Return whole request</button></div>
          {row.submission_version == null && <p className="management-notice management-notice--warning" style={{ marginTop: 14 }}>Legacy context is unknown. This version can be returned for fresh evidence, but cannot be approved.</p>}
        </section>
      </>}
      {decision && decision.id === selected && <fieldset className="management-confirmation"><legend>Confirm {decision.kind === "approve" ? "approval" : "return"} of request {decision.id}, version {decision.version ?? "Unknown legacy"}</legend>
        {decision.kind === "return" ? <label className="management-field">What needs correction?<textarea aria-label="Return reason" maxLength={500} value={reason} onChange={event => setReason(event.target.value)} placeholder="Explain what the Student should check or update." /></label> : <p>Apply all proposed changes shown for this version after checking the submitted COR.</p>}
        <div className="management-actions"><button className="management-button" disabled={busy} onClick={() => setDecision(null)}>Cancel</button><button id="confirm-correction-decision" className="management-button management-button--primary" disabled={busy || (decision.kind === "return" ? !reason.trim() : !canApprove)} onClick={decide}>{busy ? "Saving…" : "Confirm decision"}</button></div>
      </fieldset>}
      {error && <p role="alert" className="management-notice management-notice--error">{error}</p>}
      {data && <section className="management-action-section"><h3 className="management-section-title">Recent version history</h3>
        <ul className="management-history">{data.history.map(item => <li key={item.change_request_id}><button onClick={() => select(item.change_request_id)}>Version {item.submission_version ?? "Unknown legacy"}: {item.status}</button><span> · {dateText(item.created_at)}</span></li>)}</ul>
        <button className="management-button" style={{ marginTop: 14 }} onClick={() => { const root = row.root_change_request_id || row.change_request_id; select(null); list.filter("status", ""); list.filter("root_change_request_id", root); }}>Browse complete history</button>
      </section>}
    </ManagementDialog>}
  </ManagementPage>;
}
