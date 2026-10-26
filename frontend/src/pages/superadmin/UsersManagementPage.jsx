import { useState } from "react";
import { request } from "../../services/apiClient";
import { useToast } from "../../components/feedback";
import { dateText, LoadState, Pagination, usePagedRecords, useRecord, valueText } from "../../features/accounts/management";
import { ManagementPage, ManagementPanel, ManagementDialog, ManagementBadge, ManagementDetail } from "../../features/accounts/SuperadminLayout";
import CounselorAccountForm from "../../features/accounts/CounselorAccountForm";

const FILTERS = [
  ["role_code", "Role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN"]],
  ["account_status", "Enrollment status", ["ACTIVE", "PENDING_VERIFICATION", "VERIFICATION_EXPIRED"]],
  ["is_deactivated", "Sign-in access", [["false", "Enabled"], ["true", "Deactivated"]]],
];
const fullName = record => [record.first_name, record.middle_name, record.last_name].filter(Boolean).join(" ");
const roleTone = role => role === "SUPERADMIN" ? "purple" : role === "GUIDANCE_STAFF" ? "blue" : role === "COUNSELOR" ? "success" : "neutral";

export default function UsersManagementPage({ user }) {
  const list = usePagedRecords("/accounts/users", { q: "", role_code: "", account_status: "", is_deactivated: "" });
  const [selected, setSelected] = useState(null);
  const detail = useRecord(selected ? "/accounts/users/" + selected : null);
  const [confirmation, setConfirmation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState(null);
  const [editorBusy, setEditorBusy] = useState(false);
  const toast = useToast();
  function close() { setSelected(null); setConfirmation(null); setError(""); }
  function filter(key, value) { close(); list.filter(key, value); }
  function cancelEditor() { const id = editor?.record?.user_id; setEditor(null); if (id) setSelected(id); }
  async function changeStatus() {
    const action = confirmation;
    setBusy(true); setError("");
    try {
      await request("/accounts/users/" + action.id + "/" + (action.deactivated ? "deactivate" : "reactivate"), { method: "POST", body: "{}" });
      setConfirmation(null); list.reload(); detail.reload();
      toast.success("Account status updated.");
    } catch (failure) { setError(failure.message); detail.reload(); }
    finally { setBusy(false); }
  }
  const record = detail.data;
  return <ManagementPage title="Users" icon="users" description="Manage account access and view registered information. Enrollment and sign-in access are managed separately."
    actions={<><a href="#student-directory" className="management-button">Student directory & recovery</a><button className="management-button management-button--primary" onClick={() => { close(); setEditor({ record: null }); }}>Create Counselor</button></>}>
    <ManagementPanel>
      <form className="management-filters" onSubmit={event => event.preventDefault()}>
        <label className="management-field">Search accounts
          <input aria-label="Search users" type="search" value={list.filters.q} maxLength={320} onChange={event => filter("q", event.target.value)} placeholder="Name, email or Student Number" />
        </label>
        {FILTERS.map(([field, title, choices]) => <label key={field} className="management-field">{title}
          <select aria-label={title} value={list.filters[field]} onChange={event => filter(field, event.target.value)}>
            <option value="">All</option>{choices.map(choice => {
              const [value, text] = Array.isArray(choice) ? choice : [choice, choice.replaceAll("_", " ")];
              return <option key={value} value={value}>{text}</option>;
            })}
          </select>
        </label>)}
      </form>
    </ManagementPanel>

    <ManagementPanel title="Account directory" description="Select an account to view details or manage sign-in access."
      actions={!list.loading && !list.error && <span className="management-count"><strong>{list.total}</strong> account{list.total === 1 ? "" : "s"}</span>}>
      {(list.loading || list.error || list.items.length === 0) && <div className="management-state"><LoadState state={list} empty="No accounts match these filters." /></div>}
      <div className="management-table-scroll">
        <table className="management-table"><caption className="sr-only">Account directory</caption>
          <thead><tr>{["Name", "Email", "Role", "Enrollment", "Sign-in access", "Details"].map(title => <th key={title} scope="col">{title}</th>)}</tr></thead>
          <tbody>{list.items.map(item => <tr key={item.user_id}>
            <td><div className="management-person"><span className="management-avatar" aria-hidden="true">{(item.first_name?.[0] || "") + (item.last_name?.[0] || "")}</span><div><div className="management-name">{fullName(item)}</div>{item.student_number && <span className="management-subtext">{item.student_number}</span>}</div></div></td>
            <td>{item.email}</td>
            <td><ManagementBadge value={item.role_code} tone={roleTone(item.role_code)} /></td>
            <td><ManagementBadge value={item.account_status} /></td>
            <td><ManagementBadge value={item.is_deactivated ? "Deactivated" : "Enabled"} /></td>
            <td><button className="management-button" id={"user-open-" + item.user_id} onClick={() => { setSelected(item.user_id); setConfirmation(null); setError(""); }}>Details</button></td>
          </tr>)}</tbody>
        </table>
      </div>
      <Pagination state={list} name="Users" />
    </ManagementPanel>

    {selected && <ManagementDialog label="User details" title={record ? fullName(record) : "Account details"} subtitle={record ? record.email : "Loading account…"} onClose={close}>
      <LoadState state={detail} />
      {record && <>
        <div className="management-actions"><ManagementBadge value={record.role_code} tone={roleTone(record.role_code)} /><ManagementBadge value={record.account_status} /><ManagementBadge value={record.is_deactivated ? "Deactivated" : "Enabled"} /></div>
        {record.role_code === "COUNSELOR" && <div className="management-actions"><button className="management-button" id={`counselor-edit-${record.user_id}`} onClick={() => { close(); setEditor({ record }); }}>Edit Counselor account</button></div>}
        <section><h3 className="management-section-title">Account information</h3><dl className="management-detail-grid">
          <ManagementDetail label="Role">{record.role_code.replaceAll("_", " ")}</ManagementDetail>
          <ManagementDetail label="Enrollment">{record.account_status.replaceAll("_", " ")}</ManagementDetail>
          <ManagementDetail label="Sign-in access">{record.is_deactivated ? "Deactivated" : "Enabled"}</ManagementDetail>
          <ManagementDetail label="Account ID">{record.user_id}</ManagementDetail>
          <ManagementDetail label="Created">{dateText(record.created_at)}</ManagementDetail>
          <ManagementDetail label="Updated">{dateText(record.updated_at)}</ManagementDetail>
        </dl></section>
        {(record.role_code === "STUDENT" || record.profile) && <section><h3 className="management-section-title">Academic profile</h3><dl className="management-detail-grid">
          <ManagementDetail label="Student Number">{valueText(record.student_number)}</ManagementDetail>
          <ManagementDetail label="Campus">{valueText(record.campus_name)}</ManagementDetail>
          <ManagementDetail label="Program">{valueText(record.program_name)}</ManagementDetail>
          <ManagementDetail label="Year">{valueText(record.profile?.year_level)}</ManagementDetail>
          <ManagementDetail label="Section">{valueText(record.profile?.section)}</ManagementDetail>
          <ManagementDetail label="Valid until">{valueText(record.valid_until)}</ManagementDetail>
        </dl></section>}
        <section className="management-action-section"><h3 className="management-section-title">Sign-in access</h3>
          {["STUDENT", "COUNSELOR"].includes(record.role_code) && record.user_id !== user?.user_id
            ? <><p className="management-description" style={{ marginBottom: 14 }}>Manage access to CounselConnect. This does not change enrollment, appointments or registered information.</p><button className={"management-button " + (record.is_deactivated ? "management-button--primary" : "management-button--danger")} disabled={busy} id={"user-status-" + record.user_id} onClick={() => setConfirmation({ id: record.user_id, deactivated: !record.is_deactivated, name: record.first_name + " " + record.last_name + " (" + record.email + ")" })}>{record.is_deactivated ? "Reactivate account" : "Deactivate account"}</button></>
            : <p className="management-notice">Account status changes are unavailable for this role.</p>}
        </section>
      </>}
      {confirmation && confirmation.id === selected && <fieldset className="management-confirmation"><legend>Confirm {confirmation.deactivated ? "deactivation" : "reactivation"}: {confirmation.name}</legend>
        <p>{confirmation.deactivated ? "Sign-in access will be disabled and active sessions revoked." : "Sign-in access will be enabled. The user must sign in again; enrollment restrictions remain."} Appointments and registered information remain unchanged.</p>
        <div className="management-actions"><button className="management-button" disabled={busy} onClick={() => setConfirmation(null)}>Cancel</button><button id="confirm-user-status" className={"management-button " + (confirmation.deactivated ? "management-button--danger" : "management-button--primary")} disabled={busy} onClick={changeStatus}>{busy ? "Saving…" : "Confirm status change"}</button></div>
      </fieldset>}
      {error && <p role="alert" className="management-notice management-notice--error">{error}</p>}
    </ManagementDialog>}
    {editor && <ManagementDialog label={editor.record ? "Edit Counselor" : "Create Counselor"} title={editor.record ? "Edit Counselor account" : "New Counselor account"} subtitle={editor.record ? fullName(editor.record) : "Add a Counselor to CounselConnect"} closeDisabled={editorBusy} onClose={cancelEditor}>
      <CounselorAccountForm key={editor.record?.user_id || "new"} record={editor.record} busy={editorBusy} onBusyChange={setEditorBusy} onCancel={cancelEditor} onSaved={id => { setEditor(null); setSelected(id); list.reload(); detail.reload(); toast.success(editor.record ? "Counselor account updated." : "Counselor account created."); }} />
    </ManagementDialog>}
  </ManagementPage>;
}
