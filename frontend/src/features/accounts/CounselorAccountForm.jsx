import { useState } from "react";
import { request } from "../../services/apiClient";

export default function CounselorAccountForm({ record = null, busy, onBusyChange, onSaved, onCancel }) {
  const [fields, setFields] = useState(() => ({ first_name: record?.first_name || "", middle_name: record?.middle_name || "", last_name: record?.last_name || "", email: record?.email || "" }));
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setError("");
    if (!record && password !== confirmation) { setError("The passwords do not match."); return; }
    onBusyChange(true);
    try {
      const result = await request(record ? `/accounts/users/${record.user_id}` : "/accounts/users", {
        method: record ? "PATCH" : "POST",
        body: JSON.stringify({ ...fields, middle_name: fields.middle_name.trim() || null,
          ...(record ? { expected_updated_at: record.updated_at } : { password }) }),
      });
      setPassword(""); setConfirmation(""); onSaved(result.user_id);
    } catch (failure) { setError(failure.message); }
    finally { onBusyChange(false); }
  }
  return <form aria-label={record ? "Edit counselor account" : "Create counselor account"} onSubmit={submit}>
    <p className="management-notice">{record ? "An email change signs this Counselor out of all active sessions. They must sign in again with their new email." : "The new Counselor can sign in immediately. Share the initial password privately; it will not be displayed after creation."}</p>
    <div className="management-account-fields">
      {[["first_name", "First name"], ["middle_name", "Middle name (optional)"], ["last_name", "Last name"], ["email", "Email"]].map(([key, title]) => <label key={key} className="management-field" htmlFor={`counselor-${key}`}>{title}
        <input id={`counselor-${key}`} type={key === "email" ? "email" : "text"} autoComplete={key === "email" ? "email" : "off"} maxLength={key === "email" ? 320 : 100} required={key !== "middle_name"} disabled={busy} value={fields[key]} onChange={event => setFields(old => ({ ...old, [key]: event.target.value }))} />
      </label>)}
      {!record && <>
        <div className="management-field"><label htmlFor="counselor-password">Initial password</label><input id="counselor-password" type="password" autoComplete="new-password" aria-describedby="counselor-password-help" required minLength={8} maxLength={128} disabled={busy} value={password} onChange={event => setPassword(event.target.value)} /><span id="counselor-password-help" className="management-muted">8–128 characters</span></div>
        <label className="management-field" htmlFor="counselor-confirm-password">Confirm password<input id="counselor-confirm-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} disabled={busy} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
      </>}
    </div>
    {error && <p role="alert" className="management-notice management-notice--error">{error}</p>}
    <div className="management-actions management-action-section"><button type="button" className="management-button" disabled={busy} onClick={onCancel}>Cancel</button><button type="submit" className="management-button management-button--primary" disabled={busy}>{busy ? "Saving…" : record ? "Save Counselor changes" : "Create Counselor"}</button></div>
  </form>;
}
