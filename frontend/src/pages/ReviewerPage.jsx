import { useState } from "react";
import { useReviewerConsole } from "../features/enrollment";

const STATUS_STYLES = {
  PENDING: "bg-amber-100 text-amber-700",
  APPROVED: "bg-emerald-100 text-emerald-700",
  REJECTED: "bg-red-100 text-red-700",
  EXPIRED: "bg-slate-200 text-slate-600",
  NEEDS_RESUBMISSION: "bg-blue-100 text-blue-700",
};

/**
 * Counselor review console (DFD 1.3): registration applications.
 * "Pending" tab: approve / reject-with-comment with COR PDF preview.
 * "History" tab: PERMANENT record of every application and its decision.
 *
 * Auth (ADR-019): requires a signed-in COUNSELOR session (enforced by
 * the backend). There is no admin role — the Counselor is the authority.
 */
export default function ReviewerPage() {
  const {
    queue,
    history,
    historyFilter,
    setHistoryFilter,
    loading,
    message,
    toast,
    approve,
    reject,
    openCorPdf,
  } = useReviewerConsole();
  const [tab, setTab] = useState("pending");
  const [comments, setComments] = useState({});

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Registration review</h1>
          <p className="text-xs text-slate-500">
            Guidance Counselor console — applications and permanent decisions (DFD 1.3)
          </p>
        </div>
        <a href="#landing" className="text-xs text-slate-400 hover:underline">
          Back to landing
        </a>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-8">

        <div className="mt-6 flex gap-2 border-b border-slate-200">
          <button
            onClick={() => setTab("pending")}
            className={`px-4 py-2 text-sm font-medium ${
              tab === "pending"
                ? "border-b-2 border-emerald-600 text-emerald-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Pending ({queue.length})
          </button>
          <button
            onClick={() => setTab("history")}
            className={`px-4 py-2 text-sm font-medium ${
              tab === "history"
                ? "border-b-2 border-emerald-600 text-emerald-700"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            All applications ({history.length})
          </button>
        </div>

        {message && (
          <p className="mt-4 rounded-md bg-slate-100 p-3 text-sm text-slate-700">{message}</p>
        )}
        {loading && <p className="mt-6 text-sm text-slate-400">Loading…</p>}

        {/* Decision feedback — persists 8s, independent of the list refresh */}
        {toast && (
          <div
            className={`fixed bottom-6 right-6 z-50 max-w-sm rounded-lg px-5 py-4 text-sm font-medium shadow-lg ${
              toast.kind === "ok" ? "bg-emerald-600 text-white" : "bg-amber-500 text-white"
            }`}
          >
            {toast.text}
          </div>
        )}

        {/* ------------------------------ PENDING TAB ---------------- */}
        {tab === "pending" && !loading && queue.length === 0 && (
          <p className="mt-6 rounded-md border border-slate-200 bg-white p-6 text-center text-sm text-slate-400">
            No pending applications.
          </p>
        )}

        {tab === "pending" && (
          <div className="mt-6 space-y-6">
            {queue.map(({ verification, student, file }) => (
              <article
                key={verification.verification_id}
                className="rounded-lg border border-slate-200 bg-white p-6"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="font-semibold text-slate-800">
                      {student.first_name} {student.middle_name} {student.last_name}
                    </h2>
                    <p className="text-sm text-slate-500">{student.email}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      Submitted {new Date(verification.submitted_at).toLocaleString()}
                      {file ? ` · PDF ${(file.size_bytes / 1024 / 1024).toFixed(2)} MB` : ""}
                    </p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_STYLES.PENDING}`}>
                    PENDING
                  </span>
                </div>

                {file && (
                  <div className="mt-4">
                    <button
                      onClick={() => openCorPdf(verification.verification_id)}
                      className="text-sm font-medium text-emerald-600 hover:underline"
                    >
                      View registration form (COR) PDF ↗
                    </button>
                  </div>
                )}

                <div className="mt-4 flex flex-wrap items-start gap-3">
                  <button
                    onClick={() => approve(verification.verification_id)}
                    className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                  >
                    Approve
                  </button>
                  <div className="min-w-[240px] flex-1">
                    <input
                      type="text"
                      placeholder="Rejection comment (required to reject)"
                      value={comments[verification.verification_id] ?? ""}
                      onChange={(e) =>
                        setComments((c) => ({
                          ...c,
                          [verification.verification_id]: e.target.value,
                        }))
                      }
                      className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <button
                    onClick={() =>
                      reject(verification.verification_id, comments[verification.verification_id] ?? "")
                    }
                    className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
                  >
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}

        {/* ------------------------------ HISTORY TAB ---------------- */}
        {tab === "history" && (
          <>
            <div className="mt-4 flex items-center gap-2">
              <label className="text-sm text-slate-500">Filter:</label>
              {["", "PENDING", "APPROVED", "REJECTED", "EXPIRED"].map((s) => (
                <button
                  key={s || "ALL"}
                  onClick={() => setHistoryFilter(s)}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    historyFilter === s
                      ? "bg-emerald-600 text-white"
                      : "bg-white text-slate-600 border border-slate-300"
                  }`}
                >
                  {s || "ALL"}
                </button>
              ))}
            </div>

            {!loading && history.length === 0 && (
              <p className="mt-6 rounded-md border border-slate-200 bg-white p-6 text-center text-sm text-slate-400">
                No applications in this view yet.
              </p>
            )}

            <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Applicant</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Submitted</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Decision</th>
                    <th className="px-4 py-3">Comment / Validity</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(({ verification, student }) => (
                    <tr key={verification.verification_id} className="border-b border-slate-100">
                      <td className="px-4 py-3 font-medium text-slate-700">
                        {student.first_name} {student.last_name}
                      </td>
                      <td className="px-4 py-3 text-slate-500">{student.email}</td>
                      <td className="px-4 py-3 text-slate-500">
                        {new Date(verification.submitted_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            STATUS_STYLES[verification.status] ?? "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {verification.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {verification.decision_at
                          ? new Date(verification.decision_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-500">
                        {verification.status === "APPROVED"
                          ? `Valid until ${verification.valid_until ?? "—"}`
                          : verification.reviewer_note ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-400">
              COR files are permanently deleted after each decision (privacy boundary);
              the decision record itself is kept permanently.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
