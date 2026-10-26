import { useState } from "react";
import { useUserDirectory, useProfileChangeRequests } from "../../features/accounts";
import { useToast } from "../../components/feedback";
import { request } from "../../services/apiClient";
import { ManagementHeader, ManagementDialog, ManagementBadge } from "../../features/accounts/SuperadminLayout";
import { dateText } from "../../features/accounts/management";

const SCREENING_STATUSES = [
  "AWAITING_CONFIRMATION",
  "NEEDS_RESUBMISSION",
  "PASSED",
  "FAILED",
  "PROCESSING",
];

const STATUS_STYLES = {
  PASSED: "bg-emerald-100 text-emerald-800",
  AWAITING_CONFIRMATION: "bg-amber-100 text-amber-800",
  NEEDS_RESUBMISSION: "bg-blue-100 text-blue-800",
  FAILED: "bg-red-100 text-red-800",
  PROCESSING: "bg-slate-200 text-slate-700",
};

const ACCOUNT_STYLES = {
  ACTIVE: "bg-emerald-100 text-emerald-800",
  PENDING_VERIFICATION: "bg-amber-100 text-amber-800",
  VERIFICATION_EXPIRED: "bg-slate-200 text-slate-700",
};

function Badge({ value, styles, polished = false }) {
  if (polished) return <ManagementBadge value={value} />;
  if (!value) return <span className="text-slate-500">—</span>;
  return (
    <span className={"rounded-full px-2 py-0.5 text-xs font-semibold " + (styles[value] ?? "bg-slate-100 text-slate-700")}>
      {value.replaceAll("_", " ")}
    </span>
  );
}

const text = (value) => (value === null || value === undefined || value === "" ? "—" : String(value));

function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? text(value) : date.toLocaleString();
}

function DetailRow({ label, value }) {
  return (
    <div className="directory-detail-row flex flex-col gap-0.5 border-b border-slate-100 py-2 sm:flex-row sm:items-baseline sm:gap-3">
      <dt className="w-48 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="break-words text-sm text-slate-800">{value}</dd>
    </div>
  );
}

function StudentDetailModal({ item, campusName, programName, onClose, polished = false }) {
  const { user, profile, screening } = item;
  const fullName = [user.first_name, user.middle_name, user.last_name].filter(Boolean).join(" ") || "—";
  const displayDateTime = polished ? dateText : formatDateTime;
  const details = <>
        <section className="mb-4">
          <h3 className="mb-1 text-sm font-bold text-slate-700">Account</h3>
          <dl>
            <DetailRow label="User ID" value={text(user.user_id)} />
            <DetailRow label="Role" value={text(user.role_code)} />
            <DetailRow label="Account status" value={<Badge polished={polished} value={user.account_status} styles={ACCOUNT_STYLES} />} />
            <DetailRow label="Registered" value={displayDateTime(user.created_at)} />
            <DetailRow label="Last updated" value={displayDateTime(user.updated_at)} />
          </dl>
        </section>

        <section className="mb-4">
          <h3 className="mb-1 text-sm font-bold text-slate-700">Academic profile</h3>
          {profile ? (
            <dl>
              <DetailRow label="Student number" value={text(profile.student_number)} />
              <DetailRow label="Campus" value={campusName(profile.campus_id)} />
              <DetailRow label="Program" value={programName(profile.program_id)} />
              <DetailRow label="Year level" value={text(profile.year_level)} />
              <DetailRow label="Section" value={text(profile.section)} />
            </dl>
          ) : (
            <p className="py-2 text-sm text-slate-600">No confirmed academic profile yet.</p>
          )}
        </section>

        <section>
          <h3 className="mb-1 text-sm font-bold text-slate-700">Latest COR screening</h3>
          {screening ? (
            <dl>
              <DetailRow label="Status" value={<Badge polished={polished} value={screening.status} styles={STATUS_STYLES} />} />
              <DetailRow label="Failure code" value={text(screening.failure_reason_code)} />
              <DetailRow label="Template version" value={text(screening.format_template_version)} />
              <DetailRow label="Format score" value={text(screening.format_match_score)} />
              <DetailRow label="Extraction confidence" value={text(screening.extraction_confidence)} />
              <DetailRow label="Barcode status" value={text(screening.barcode_status)} />
              <DetailRow label="Barcode symbology" value={text(screening.barcode_symbology)} />
              <DetailRow label="Extracted student number" value={text(screening.extracted_student_number)} />
              <DetailRow label="Extracted name" value={text([screening.extracted_first_name, screening.extracted_middle_name, screening.extracted_last_name].filter(Boolean).join(" "))} />
              <DetailRow label="Extracted campus / program" value={`${text(screening.extracted_campus_id)} / ${text(screening.extracted_program_id)}`} />
              <DetailRow label="Extracted year / section" value={`${text(screening.extracted_year_level)} / ${text(screening.extracted_section)}`} />
              <DetailRow label="Extracted academic period" value={text(screening.extracted_academic_period)} />
              <DetailRow label="Enrollment valid until" value={text(screening.valid_until)} />
              <DetailRow label="Submitted" value={displayDateTime(screening.submitted_at)} />
              <DetailRow label="Processed" value={displayDateTime(screening.processed_at)} />
              <DetailRow label="Confirmed" value={displayDateTime(screening.confirmed_at)} />
            </dl>
          ) : (
            <p className="py-2 text-sm text-slate-600">No COR screening recorded.</p>
          )}
        </section>
  </>;
  if (polished) return <ManagementDialog label="Student details" title={fullName} subtitle={text(user.email) + " · Student #" + text(profile?.student_number)} onClose={onClose}>
    <div className="management-recovery-detail">{details}</div>
  </ManagementDialog>;
  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Student details"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div className="signup-card" style={{ maxWidth: "720px" }}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{fullName}</h2>
            <p className="text-sm text-slate-600">{text(user.email)} · Student #{text(profile?.student_number)}</p>
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            <i className="fa-solid fa-xmark" aria-hidden="true"></i>
          </button>
        </div>

        {details}
      </div>
    </div>
  );
}

/**
 * Counselor "Users" directory — read-only list of Student accounts with their
 * latest automated COR screening result (ADR-029). Backend authorized.
 * Selecting a row opens the complete profile + screening record. The Superadmin
 * also sees the pending profile-edit request queue (ADR-032).
 */
function changeLines(row) {
  const cr = row.change_request;
  const currentName = [row.current_first_name, row.current_middle_name, row.current_last_name]
    .filter(Boolean).join(" ");
  const requestedName = [cr.requested_first_name, cr.requested_middle_name, cr.requested_last_name]
    .filter(Boolean).join(" ");
  const lines = [];
  if (currentName !== requestedName) lines.push({ label: "Name", from: currentName, to: requestedName });
  if ((row.current_year_level ?? null) !== cr.requested_year_level) {
    lines.push({ label: "Year level", from: row.current_year_level ?? "—", to: cr.requested_year_level });
  }
  if ((row.current_section ?? null) !== cr.requested_section) {
    lines.push({ label: "Section", from: row.current_section ?? "—", to: cr.requested_section });
  }
  return lines;
}

function PendingEditRequests() {
  const { items, loading, error, busyId, load, approve, reject } = useProfileChangeRequests(true);
  const toast = useToast();
  const [returningId, setReturningId] = useState(null);
  const [reason, setReason] = useState("");

  async function handleApprove(changeRequestId, submissionVersion) {
    const result = await approve(changeRequestId, submissionVersion);
    if (result.success) toast.success("Profile edit approved.", { title: "Edit request" });
    else toast.error(result.message, { title: "Approval failed" });
  }

  async function handleReturn(changeRequestId, submissionVersion) {
    if (!reason.trim()) {
      toast.error("Explain what needs to be corrected.", { title: "Reason required" });
      return;
    }
    const result = await reject(changeRequestId, reason.trim(), submissionVersion);
    if (result.success) {
      toast.success("Profile edit returned for correction.", { title: "Edit request" });
      setReturningId(null);
      setReason("");
    } else {
      toast.error(result.message, { title: "Return failed" });
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-slate-900">Pending edit requests</h2>
        <button type="button" className="linklike" onClick={() => void load()}>Refresh</button>
      </div>
      <p className="mt-1 text-sm text-slate-600">
        Student-requested changes to names, year level, or section. Approving applies them.
      </p>

      {error && (
        <div role="alert" className="form-message error mt-3">
          {error} <button type="button" className="linklike" onClick={() => void load()}>Retry</button>
        </div>
      )}
      {loading && <p className="mt-3 text-sm text-slate-600" role="status">Loading edit requests…</p>}
      {!loading && !error && items.length === 0 && (
        <p className="mt-3 text-sm text-slate-600">No pending edit requests.</p>
      )}

      {!loading && items.map((row) => {
        const cr = row.change_request;
        const lines = changeLines(row);
        return (
          <div key={cr.change_request_id} className="mt-4 rounded-lg border border-slate-200 p-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <div className="font-medium text-slate-800">
                  {[row.student.first_name, row.student.last_name].filter(Boolean).join(" ") || row.student.email}
                </div>
                <div className="text-xs text-slate-600">{row.student.email} · #{row.student.user_id}</div>
              </div>
              <div className="text-xs text-slate-500">Requested {formatDateTime(cr.created_at)}</div>
            </div>

            <dl className="mt-2">
              {lines.map((line) => (
                <div key={line.label} className="flex flex-col gap-0.5 border-b border-slate-100 py-1 sm:flex-row sm:gap-3">
                  <dt className="w-28 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">{line.label}</dt>
                  <dd className="text-sm text-slate-800">
                    <span className="text-slate-400 line-through">{line.from}</span>
                    {" → "}
                    <span className="font-medium">{line.to}</span>
                  </dd>
                </div>
              ))}
            </dl>

            {returningId === cr.change_request_id ? (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <input
                  id={`edit-reason-${cr.change_request_id}`}
                  type="text"
                  maxLength={500}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="What needs to be corrected?"
                  className="form-input max-w-xs"
                />
                <button
                  id={`edit-reject-confirm-${cr.change_request_id}`}
                  type="button"
                  className="rounded-md border border-red-300 px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-60"
                  disabled={busyId === cr.change_request_id}
                  onClick={() => handleReturn(cr.change_request_id, cr.submission_version)}
                >
                  {busyId === cr.change_request_id ? "Returning…" : "Confirm return"}
                </button>
                <button type="button" className="linklike" onClick={() => { setReturningId(null); setReason(""); }}>
                  Cancel
                </button>
              </div>
            ) : (
              <div className="mt-3 flex gap-2">
                <button
                  id={`edit-approve-${cr.change_request_id}`}
                  type="button"
                  className="rounded-md border border-emerald-300 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-50 disabled:opacity-60"
                  disabled={busyId === cr.change_request_id || !Number.isInteger(cr.submission_version) || cr.submission_version < 1}
                  title={cr.submission_version == null ? "Approval requires a recorded submission version." : undefined}
                  onClick={() => handleApprove(cr.change_request_id, cr.submission_version)}
                >
                  {busyId === cr.change_request_id ? "Approving…" : "Approve"}
                </button>
                <button
                  id={`edit-reject-${cr.change_request_id}`}
                  type="button"
                  className="rounded-md border border-red-300 px-2.5 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                  onClick={() => { setReturningId(cr.change_request_id); setReason(""); }}
                >
                  Return
                </button>
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}

export default function CounselorUsersPage({ canRecover = false, showCorrections = true }) {
  const {
    items,
    total,
    page,
    pageCount,
    query,
    status,
    loading,
    error,
    campusName,
    programName,
    search,
    filterStatus,
    setPage,
    retry,
  } = useUserDirectory();
  const toast = useToast();
  const [term, setTerm] = useState(query);
  const [selected, setSelected] = useState(null);
  const [recovering, setRecovering] = useState(null);

  async function handleRecover(user) {
    setRecovering(user.user_id);
    try {
      await request(`/accounts/students/${user.user_id}/recover`, { method: "POST", body: "{}" });
      toast.success(`Recovered ${user.email}. They can now re-upload their COR.`, { title: "Account recovery" });
      retry();
    } catch (err) {
      toast.error(err?.message ?? "Could not recover this account.", { title: "Recovery failed" });
    } finally {
      setRecovering(null);
    }
  }

  return (
    <main className={canRecover ? "superadmin-page" : "home-page"}>
      <section className={canRecover ? "management-workspace" : "px-4 pt-8 sm:px-6 lg:px-8"}>
        {canRecover && <ManagementHeader title="Student Directory" icon="recovery" description="View registration records and help eligible Students begin a fresh COR submission."><a href="#users" className="management-button">Back to Users</a></ManagementHeader>}
        <div className={canRecover ? "management-panel" : "mx-auto max-w-6xl"}>
          {canRecover ? <header className="management-panel-header"><div><h2>Registration & account recovery</h2><p>Recovery is available for non-active accounts. Existing sign-in restrictions still apply.</p></div>{!loading && !error && <span className="management-count"><strong>{total}</strong> students</span>}</header> : <>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Users</h1>
              <p className="mt-1 text-sm text-slate-600">
                Student accounts and their latest COR screening result. Read-only.
              </p>
            </div>
            <p className="text-sm text-slate-600">{total} student{total === 1 ? "" : "s"}</p>
          </div>
          </>}

          {canRecover && showCorrections && <PendingEditRequests />}

          <form
            className={canRecover ? "management-recovery-filters" : "mt-5 flex flex-wrap items-center gap-3"}
            onSubmit={(event) => {
              event.preventDefault();
              search(term);
            }}
          >
            <label className={canRecover ? "management-field" : "sr-only"} htmlFor="user-search">Search users</label>
            <input
              id="user-search"
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search student number, name, or email"
              className="form-input w-full max-w-md"
            />
            <label className={canRecover ? "management-field" : "sr-only"} htmlFor="user-status">Screening status</label>
            <select
              id="user-status"
              value={status}
              onChange={(event) => filterStatus(event.target.value)}
              className="form-select"
            >
              <option value="">All screening statuses</option>
              {SCREENING_STATUSES.map((value) => (
                <option key={value} value={value}>{value.replaceAll("_", " ")}</option>
              ))}
            </select>
            <button type="submit" className={canRecover ? "management-button management-button--primary" : "btn-submit btn-success"}>Search</button>
          </form>

          {error && (
            <div role="alert" className="form-message error mt-4">
              {error}{" "}
              <button type="button" className="linklike" onClick={retry}>Retry</button>
            </div>
          )}

          <div className={canRecover ? "management-table-scroll" : "mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white"}>
            <table className={canRecover ? "management-table" : "min-w-full divide-y divide-slate-200 text-sm"}>
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Student #</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Campus / Program</th>
                  <th className="px-4 py-3">Year / Section</th>
                  <th className="px-4 py-3">Account</th>
                  <th className="px-4 py-3">Screening</th>
                  <th className="px-4 py-3">Format</th>
                  <th className="px-4 py-3">Barcode</th>
                  <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading && (
                  <tr><td colSpan={9} className="px-4 py-6 text-center text-slate-600">Loading users…</td></tr>
                )}
                {!loading && items.length === 0 && !error && (
                  <tr><td colSpan={9} className="px-4 py-6 text-center text-slate-600">No students found.</td></tr>
                )}
                {!loading && items.map((item) => {
                  const { user, profile, screening } = item;
                  return (
                    <tr key={user.user_id} className="align-top">
                      <td className="px-4 py-3 font-medium text-slate-700">
                        {profile?.student_number ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800">
                          {[user.first_name, user.last_name].filter(Boolean).join(" ") || "—"}
                        </div>
                        <div className="text-xs text-slate-600">{user.email}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {profile ? (
                          <>
                            <div>{campusName(profile.campus_id)}</div>
                            <div className="text-xs text-slate-600">{programName(profile.program_id)}</div>
                          </>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {profile ? `${profile.year_level} · ${profile.section}` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge polished={canRecover} value={user.account_status} styles={ACCOUNT_STYLES} />
                      </td>
                      <td className="px-4 py-3">
                        <Badge polished={canRecover} value={screening?.status} styles={STATUS_STYLES} />
                        {screening?.failure_reason_code && (
                          <div className="mt-1 text-xs text-slate-600">
                            {screening.failure_reason_code.replaceAll("_", " ").toLowerCase()}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {screening?.format_match_score ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {screening?.barcode_status ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            className={canRecover ? "management-button" : "rounded-md border border-blue-300 px-2.5 py-1 text-xs font-semibold text-blue-800 hover:bg-blue-50"}
                            onClick={() => setSelected(item)}
                          >
                            View
                          </button>
                          {canRecover && user.account_status !== "ACTIVE" && (
                            <button
                              type="button"
                              disabled={recovering === user.user_id}
                              className="management-button management-button--quiet"
                              onClick={() => handleRecover(user)}
                            >
                              {recovering === user.user_id ? "Recovering…" : "Recover"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className={canRecover ? "management-pagination" : "mt-4 flex items-center justify-between"}>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              disabled={page <= 1 || loading}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span className="text-sm text-slate-600">Page {page} of {pageCount}</span>
            <button
              type="button"
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              disabled={page >= pageCount || loading}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {selected && (
        <StudentDetailModal
          polished={canRecover}
          item={selected}
          campusName={campusName}
          programName={programName}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  );
}
