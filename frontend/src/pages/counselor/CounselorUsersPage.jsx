import { useState } from "react";
import { useUserDirectory } from "../../features/accounts";
import { useToast } from "../../components/feedback";
import { request } from "../../services/apiClient";

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

function Badge({ value, styles }) {
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
    <div className="flex flex-col gap-0.5 border-b border-slate-100 py-2 sm:flex-row sm:items-baseline sm:gap-3">
      <dt className="w-48 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="break-words text-sm text-slate-800">{value}</dd>
    </div>
  );
}

function StudentDetailModal({ item, campusName, programName, onClose }) {
  const { user, profile, screening } = item;
  const fullName = [user.first_name, user.middle_name, user.last_name].filter(Boolean).join(" ") || "—";
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

        <section className="mb-4">
          <h3 className="mb-1 text-sm font-bold text-slate-700">Account</h3>
          <dl>
            <DetailRow label="User ID" value={text(user.user_id)} />
            <DetailRow label="Role" value={text(user.role_code)} />
            <DetailRow label="Account status" value={<Badge value={user.account_status} styles={ACCOUNT_STYLES} />} />
            <DetailRow label="Registered" value={formatDateTime(user.created_at)} />
            <DetailRow label="Last updated" value={formatDateTime(user.updated_at)} />
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
              <DetailRow label="Status" value={<Badge value={screening.status} styles={STATUS_STYLES} />} />
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
              <DetailRow label="Submitted" value={formatDateTime(screening.submitted_at)} />
              <DetailRow label="Processed" value={formatDateTime(screening.processed_at)} />
              <DetailRow label="Confirmed" value={formatDateTime(screening.confirmed_at)} />
            </dl>
          ) : (
            <p className="py-2 text-sm text-slate-600">No COR screening recorded.</p>
          )}
        </section>
      </div>
    </div>
  );
}

/**
 * Counselor "Users" directory — read-only list of Student accounts with their
 * latest automated COR screening result (ADR-029). Backend authorized.
 * Selecting a row opens the complete profile + screening record.
 */
export default function CounselorUsersPage({ canRecover = false }) {
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
    <main className="home-page">
      <section className="px-4 pt-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Users</h1>
              <p className="mt-1 text-sm text-slate-600">
                Student accounts and their latest COR screening result. Read-only.
              </p>
            </div>
            <p className="text-sm text-slate-600">{total} student{total === 1 ? "" : "s"}</p>
          </div>

          <form
            className="mt-5 flex flex-wrap items-center gap-3"
            onSubmit={(event) => {
              event.preventDefault();
              search(term);
            }}
          >
            <label className="sr-only" htmlFor="user-search">Search users</label>
            <input
              id="user-search"
              type="search"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Search student number, name, or email"
              className="form-input w-full max-w-md"
            />
            <label className="sr-only" htmlFor="user-status">Screening status</label>
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
            <button type="submit" className="btn-submit btn-success">Search</button>
          </form>

          {error && (
            <div role="alert" className="form-message error mt-4">
              {error}{" "}
              <button type="button" className="linklike" onClick={retry}>Retry</button>
            </div>
          )}

          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
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
                        <Badge value={user.account_status} styles={ACCOUNT_STYLES} />
                      </td>
                      <td className="px-4 py-3">
                        <Badge value={screening?.status} styles={STATUS_STYLES} />
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
                            className="rounded-md border border-blue-300 px-2.5 py-1 text-xs font-semibold text-blue-800 hover:bg-blue-50"
                            onClick={() => setSelected(item)}
                          >
                            View
                          </button>
                          {canRecover && user.account_status !== "ACTIVE" && (
                            <button
                              type="button"
                              disabled={recovering === user.user_id}
                              className="rounded-md border border-amber-400 px-2.5 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-50 disabled:opacity-60"
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

          <div className="mt-4 flex items-center justify-between">
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
          item={selected}
          campusName={campusName}
          programName={programName}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  );
}
