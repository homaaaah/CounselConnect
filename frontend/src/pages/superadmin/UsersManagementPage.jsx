import { useState } from "react";
import { request } from "../../services/apiClient";
import { useToast } from "../../components/feedback";
import { buttonClass, primaryClass, dateText, LoadState, Pagination, usePagedRecords, useRecord, valueText } from "../../features/accounts/management";

const ROLE_STYLES = {
  STUDENT: "bg-slate-100 text-slate-700",
  COUNSELOR: "bg-emerald-100 text-emerald-800",
  GUIDANCE_STAFF: "bg-blue-100 text-blue-800",
  SUPERADMIN: "bg-purple-100 text-purple-800",
};

const ACCOUNT_STYLES = {
  ACTIVE: "bg-emerald-100 text-emerald-800",
  PENDING_VERIFICATION: "bg-amber-100 text-amber-800",
  VERIFICATION_EXPIRED: "bg-slate-200 text-slate-700",
};

const FILTERS = [
  ["role_code", "Role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN"]],
  ["account_status", "Enrollment status", ["ACTIVE", "PENDING_VERIFICATION", "VERIFICATION_EXPIRED"]],
  ["is_deactivated", "Sign-in access", [["false", "Enabled"], ["true", "Deactivated"]]],
];

function Badge({ value, styles }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <span className={"inline-block rounded-full px-2 py-0.5 text-xs font-medium " + (styles[value] ?? "bg-slate-100 text-slate-700")}>
      {String(value).replaceAll("_", " ")}
    </span>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5 border-b border-slate-100 py-2 sm:flex-row sm:items-baseline sm:gap-3">
      <dt className="w-40 shrink-0 text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="break-words text-sm text-slate-800">{value}</dd>
    </div>
  );
}

export default function UsersManagementPage({ user }) {
  const list = usePagedRecords("/accounts/users", { q: "", role_code: "", account_status: "", is_deactivated: "" });
  const [selected, setSelected] = useState(null);
  const detail = useRecord(selected ? `/accounts/users/${selected}` : null);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const toast = useToast();
  function close() { setSelected(null); setConfirmation(null); setError(""); }
  function filter(key, value) { close(); list.filter(key, value); }
  async function changeStatus() {
    const action = confirmation;
    setBusy(true); setError("");
    try {
      await request(`/accounts/users/${action.id}/${action.deactivated ? "deactivate" : "reactivate"}`, { method: "POST", body: "{}" });
      setConfirmation(null); list.reload(); detail.reload();
      toast.success("Account status updated.");
    } catch (failure) { setError(failure.message); detail.reload(); }
    finally { setBusy(false); }
  }
  const record = detail.data;
  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#207524]">Users</h1>
          <p className="mt-1 text-sm text-slate-600">Manage sign-in access independently of enrollment. <a className="linklike" href="#student-directory">Student directory and account recovery</a></p>
        </div>
        <p className="text-sm text-slate-600">{list.total} account{list.total === 1 ? "" : "s"}</p>
      </header>

      <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6">
        <form className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={(event) => event.preventDefault()}>
          <label className="text-sm text-slate-700">Search
            <input aria-label="Search users" className="form-input mt-1" value={list.filters.q} maxLength={320} onChange={(event) => filter("q", event.target.value)} placeholder="Name, email or registered Student Number" />
          </label>
          {FILTERS.map(([field, title, choices]) =>
            <label key={field} className="text-sm text-slate-700">{title}
              <select aria-label={title} className="form-select mt-1" value={list.filters[field]} onChange={(event) => filter(field, event.target.value)}>
                <option value="">All</option>
                {choices.map((choice) => {
                  const [value, text] = Array.isArray(choice) ? choice : [choice, choice.replaceAll("_", " ")];
                  return <option key={value} value={value}>{text}</option>;
                })}
              </select>
            </label>)}
        </form>
      </section>

      <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6">
        <LoadState state={list} />
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <caption className="sr-only">Account directory</caption>
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-600">
              <tr>{["Name", "Email", "Role", "Enrollment", "Sign-in access", "Details"].map((title) => <th className="px-4 py-3" key={title}>{title}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100">{list.items.map((item) => <tr className="align-top" key={item.user_id}>
              <td className="px-4 py-3 font-medium text-slate-800">{[item.first_name, item.middle_name, item.last_name].filter(Boolean).join(" ")}</td>
              <td className="px-4 py-3 text-slate-600">{item.email}</td>
              <td className="px-4 py-3"><Badge value={item.role_code} styles={ROLE_STYLES} /></td>
              <td className="px-4 py-3"><Badge value={item.account_status} styles={ACCOUNT_STYLES} /></td>
              <td className="px-4 py-3">
                <span className={"inline-block rounded-full px-2 py-0.5 text-xs font-medium " + (item.is_deactivated ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800")}>
                  {item.is_deactivated ? "Deactivated" : "Enabled"}
                </span>
              </td>
              <td className="px-4 py-3 text-right"><button className={buttonClass} id={`user-open-${item.user_id}`} onClick={() => { setSelected(item.user_id); setConfirmation(null); setError(""); }}>Details</button></td>
            </tr>)}</tbody>
          </table>
        </div>
        <Pagination state={list} name="Users" />
      </section>
    </div>

    {selected && <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="User details"
      onClick={(event) => { if (event.target === event.currentTarget) close(); }}>
      <div className="signup-card" style={{ maxWidth: "720px" }}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">{record ? `${record.first_name} ${record.last_name}` : "User details"}</h2>
            <p className="text-sm text-slate-600">{record ? record.email : "Loading account…"}</p>
          </div>
          <button type="button" className="modal-close" onClick={close} aria-label="Close">
            <i className="fa-solid fa-xmark" aria-hidden="true"></i>
          </button>
        </div>
        <LoadState state={detail} />
        {record && <section className="mb-4">
          <h3 className="mb-1 text-sm font-bold text-slate-700">Account</h3>
          <dl>
            <DetailRow label="Role" value={record.role_code} />
            <DetailRow label="Enrollment" value={record.account_status} />
            <DetailRow label="Sign-in access" value={record.is_deactivated ? "Deactivated" : "Enabled"} />
            <DetailRow label="Student Number" value={valueText(record.student_number)} />
            <DetailRow label="Campus" value={valueText(record.campus_name)} />
            <DetailRow label="Program" value={valueText(record.program_name)} />
            <DetailRow label="Year" value={valueText(record.profile?.year_level)} />
            <DetailRow label="Section" value={valueText(record.profile?.section)} />
            <DetailRow label="Valid until" value={valueText(record.valid_until)} />
            <DetailRow label="Created" value={dateText(record.created_at)} />
            <DetailRow label="Updated" value={dateText(record.updated_at)} />
          </dl>
        </section>}
        {record && <section>
          {["STUDENT", "COUNSELOR"].includes(record.role_code) && record.user_id !== user?.user_id
            ? <button className={primaryClass} disabled={busy} id={`user-status-${record.user_id}`} onClick={() => setConfirmation({ id: record.user_id, deactivated: !record.is_deactivated, name: `${record.first_name} ${record.last_name} (${record.email})` })}>{record.is_deactivated ? "Reactivate account" : "Deactivate account"}</button>
            : <p className="text-sm text-slate-500">Account status changes are unavailable for this role.</p>}
        </section>}
        {confirmation && confirmation.id === selected && <fieldset className="mt-4 space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-4"><legend className="font-semibold text-amber-900">Confirm {confirmation.deactivated ? "deactivation" : "reactivation"}: {confirmation.name}</legend>
          <p className="text-sm text-amber-900">{confirmation.deactivated ? "Sign-in access will be disabled and active sessions revoked." : "Sign-in access will be enabled. The user must sign in again; enrollment restrictions remain."} Appointments and registered information remain unchanged.</p>
          <div className="flex gap-2"><button className={buttonClass} disabled={busy} onClick={() => setConfirmation(null)}>Cancel</button><button id="confirm-user-status" className={primaryClass} disabled={busy} onClick={changeStatus}>{busy ? "Saving…" : "Confirm status change"}</button></div>
        </fieldset>}
        {error && <p role="alert" className="form-message error mt-4">{error}</p>}
      </div>
    </div>}
  </main>;
}