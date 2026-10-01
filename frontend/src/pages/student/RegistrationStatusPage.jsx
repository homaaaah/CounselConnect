import { useEffect, useState } from "react";
import {
  useCorScreening,
  confirmedFieldsFrom,
  editedEditableFields,
  failureReasonText,
} from "../../features/accounts";
import ScreeningFields from "../../features/accounts/ScreeningFields";

const STATUS_LABELS = {
  AWAITING_CONFIRMATION: "Confirm your details",
  NEEDS_RESUBMISSION: "Re-upload needed",
  FAILED: "Screening failed",
  PROCESSING: "Processing",
  PASSED: "Confirmed",
};

/**
 * RegistrationStatusPage — a signed-in student's COR screening.
 *
 * Shows the fields extracted from the COR as editable inputs (with campus and
 * program selectors), a Confirm button that activates the account, and — for
 * NEEDS_RESUBMISSION/FAILED — a COR re-upload form.
 */
export default function RegistrationStatusPage({ unmatchedCampusName, unmatchedProgramName, onRejected }) {
  const state = useCorScreening();
  const [form, setForm] = useState(null);
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (state.screening) setForm(confirmedFieldsFrom(state.screening));
  }, [state.screening]);

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleConfirm(e) {
    e.preventDefault();
    if (hasEdits) {
      await state.requestEdit(form);
      return;
    }
    await state.confirm(form);
  }

  async function handleRequestEdit() {
    await state.requestEdit(form);
  }

  async function handleRejectAccount() {
    const confirmed = typeof window === "undefined" || typeof window.confirm !== "function"
      ? true
      : window.confirm("Reject this registration? Your account and uploaded COR will be deleted.");
    if (!confirmed) {
      return;
    }
    const result = await state.rejectAccount();
    if (result?.success && onRejected) await onRejected();
  }

  async function handleResubmit(e) {
    e.preventDefault();
    const result = await state.resubmit(file);
    if (result.success) setFile(null);
  }

  const screening = state.screening;
  const confirmable = screening?.status === "AWAITING_CONFIRMATION";
  const rejectable = !screening || screening.status !== "PASSED";
  const canResubmit = !state.loading
    && (!screening || ["NEEDS_RESUBMISSION", "FAILED"].includes(screening.status));
  const editDiffs = form && confirmable ? editedEditableFields(screening, form) : [];
  const hasEdits = editDiffs.length > 0;
  const headerTitle = confirmable
    ? "Review your details"
    : canResubmit
      ? "Re-upload your COR"
      : "Your registration status";
  const headerSubtitle = confirmable
    ? "We read the details from your registration form (COR). Confirm to activate your account, or reject the account."
    : canResubmit
      ? "We could not read all of your registration form. Upload a clearer or corrected PDF to continue."
      : "Your enrollment details are on file.";
  const failureText = failureReasonText(screening?.failure_reason_code);
  const campusHint = screening && !screening.extracted_campus_id
    ? unmatchedCampusName
      ? `We could not match “${unmatchedCampusName}”. Please choose your campus.`
      : "We could not match the campus printed on your COR. Please choose one."
    : "";
  const programHint = screening && !screening.extracted_program_id
    ? unmatchedProgramName
      ? `We could not match “${unmatchedProgramName}”. Please choose your program.`
      : "We could not match the program printed on your COR. Please choose one."
    : "";

  return (
    <main className="auth-shell">
      <div className="signup-card">
        <div className="signup-header">
          <h1>{headerTitle}</h1>
          <p>{headerSubtitle}</p>
        </div>

        {state.loading && <p role="status" className="form-hint">Loading your registration status...</p>}

        {state.error && (
          <div role="alert" className="form-message error">
            {state.error}{" "}
            <button type="button" className="linklike" onClick={() => void state.load()}>Retry</button>
          </div>
        )}

        {screening && (
          <div className="form-message" role="status">
            Status: <strong>{STATUS_LABELS[screening.status] ?? screening.status}</strong>
            {failureText ? ` — ${failureText}` : ""}
          </div>
        )}

        {!state.loading && !screening && !state.error && (
          <p className="form-hint">
            No registration form (COR) was found for your account. Upload your current
            COR below to continue.
          </p>
        )}

        {screening && form && (
          <form onSubmit={handleConfirm}>
            <ScreeningFields
              form={form}
              set={set}
              campuses={state.campuses}
              programs={state.programs}
              campusHint={campusHint}
              programHint={programHint}
              referenceError={state.referenceError}
              onRetryReference={() => void state.retryReferenceData()}
              editable={confirmable}
            />

            {hasEdits && confirmable && (
              <div className="form-hint">
                Your changes will be reviewed by a Superadmin; your account activates now
                with the details printed on your COR.
              </div>
            )}
            <div className="form-actions">
              {hasEdits ? (
                <button
                  type="button"
                  onClick={handleRequestEdit}
                  disabled={state.busy || !confirmable}
                  className="btn-submit btn-success"
                >
                  {state.busy ? "Submitting…" : "Submit edit request"}
                </button>
              ) : (
                <button type="submit" disabled={state.busy || !confirmable} className="btn-submit btn-success">
                  {state.busy ? "Confirming…" : "Confirm details"}
                </button>
              )}
              <button
                type="button"
                onClick={handleRejectAccount}
                disabled={state.busy || !rejectable}
                className="btn-submit btn-danger"
              >
                Reject account
              </button>
            </div>
            {!confirmable && (
              <div className="form-hint">
                These details cannot be confirmed right now. Follow the instructions above.
              </div>
            )}
          </form>
        )}

        {canResubmit && (
          <form onSubmit={handleResubmit} encType="multipart/form-data">
            <div className="upload-box">
              <div className="upload-title">Registration form (COR) — re-upload</div>
              <div className="upload-desc">
                Upload a clearer PDF of your current Certificate of Registration. PDF only,
                max 10 MB. Stored privately and deleted after your account is activated.
              </div>
              <input
                id="resubmit-cor"
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="form-input"
              />
              {file && (
                <div className="form-hint">
                  Attached: {file.name}
                  {typeof file.size === "number" ? ` (${(file.size / 1024 / 1024).toFixed(2)} MB)` : ""}
                </div>
              )}
            </div>
            <div className="form-actions">
              <button type="submit" disabled={state.busy || !file} className="btn-danger btn-danger">
                {state.busy ? "Uploading…" : "Re-upload COR"}
              </button>
              <button
                type="button"
                onClick={handleRejectAccount}
                disabled={state.busy || !rejectable}
                className="btn-submit btn-danger"
              >
                Reject account
              </button>
            </div>
          </form>
        )}

        {state.message && (
          <div className="form-message success" role="status">
            {state.message} <a href="#home">Go to home</a>
          </div>
        )}

        <p className="footer-link" style={{ textAlign: "center" }}>
          <a href="#home">Back to home</a>
        </p>
      </div>
    </main>
  );
}
