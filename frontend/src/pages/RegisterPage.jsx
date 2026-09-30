import { useEffect, useState } from "react";
import {
  useRegistration,
  EMPTY_FORM,
  confirmedFieldsFrom,
  actionErrorMessage,
  ScreeningFields,
} from "../features/accounts";
import { request } from "../services/apiClient";

/**
 * Student registration (automated COR screening), prototype-style:
 * one card with email + password + COR; on submit the student is signed in
 * automatically and the account-confirmation step appears inline so they can
 * review the extracted details and activate the account without a separate
 * sign-in. inModal renders the same card without the full-page shell.
 */
export default function RegisterPage({ inModal = false, onClose, onSwitchToLogin, onSignedIn, onActivated, onRejected }) {
  const { register, submitting } = useRegistration();
  const [form, setForm] = useState(EMPTY_FORM);
  const [corFile, setCorFile] = useState(null);
  const [result, setResult] = useState(null);

  const [phase, setPhase] = useState("form"); // "form" | "confirm" | "done"
  const [screening, setScreening] = useState(null);
  const [unmatched, setUnmatched] = useState({ campus: null, program: null });
  const [confirmForm, setConfirmForm] = useState(null);
  const [campuses, setCampuses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [referenceError, setReferenceError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmError, setConfirmError] = useState("");

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function setConfirm(key, value) {
    setConfirmForm((f) => ({ ...f, [key]: value }));
  }

  async function loadReference() {
    setReferenceError("");
    const [campusResult, programResult] = await Promise.allSettled([
      request("/accounts/campuses"),
      request("/accounts/programs"),
    ]);
    if (campusResult.status === "fulfilled") setCampuses(campusResult.value?.items ?? []);
    if (programResult.status === "fulfilled") setPrograms(programResult.value?.items ?? []);
    if (campusResult.status !== "fulfilled" || programResult.status !== "fulfilled") {
      setReferenceError("Could not load campus/program options. Please retry.");
    }
  }

  useEffect(() => {
    if (phase === "confirm") void loadReference();
  }, [phase]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (form.password !== form.confirm_password) {
      setResult({ success: false, message: "Passwords do not match." });
      return;
    }
    const r = await register(form, corFile);
    setResult(r);
    if (r.success) {
      if (r.auth && onSignedIn) onSignedIn(r.auth);
      if (r.canConfirm) {
        setScreening(r.screening);
        setConfirmForm(confirmedFieldsFrom(r.screening));
        setUnmatched({ campus: r.unmatched_campus_name, program: r.unmatched_program_name });
        setConfirmError("");
        setPhase("confirm");
      }
    }
  }

  async function handleConfirm(e) {
    e.preventDefault();
    const missing = !confirmForm.student_number || !confirmForm.first_name || !confirmForm.last_name
      || confirmForm.campus_id === "" || confirmForm.program_id === ""
      || confirmForm.year_level === "" || !confirmForm.section;
    if (missing) {
      setConfirmError("Please complete every required field before confirming.");
      return;
    }
    setBusy(true);
    setConfirmError("");
    try {
      await request("/cor-screenings/confirm", {
        method: "POST",
        body: JSON.stringify({
          student_number: confirmForm.student_number.trim(),
          first_name: confirmForm.first_name.trim(),
          middle_name: (confirmForm.middle_name ?? "").trim() || null,
          last_name: confirmForm.last_name.trim(),
          campus_id: Number(confirmForm.campus_id),
          program_id: Number(confirmForm.program_id),
          year_level: Number(confirmForm.year_level),
          section: confirmForm.section.trim(),
          academic_period: (confirmForm.academic_period ?? "").trim() || null,
        }),
      });
      setPhase("done");
      if (onActivated) await onActivated();
    } catch (err) {
      setConfirmError(actionErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    setBusy(true);
    setConfirmError("");
    try {
      await request("/cor-screenings/reject", { method: "POST" });
      if (onRejected) {
        await onRejected();
      } else {
        window.location.hash = "registration";
      }
    } catch (err) {
      setConfirmError(actionErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const campusHint = screening && !screening.extracted_campus_id
    ? unmatched.campus
      ? `We could not match “${unmatched.campus}”. Please choose your campus.`
      : "We could not match the campus printed on your COR. Please choose one."
    : "";
  const programHint = screening && !screening.extracted_program_id
    ? unmatched.program
      ? `We could not match “${unmatched.program}”. Please choose your program.`
      : "We could not match the program printed on your COR. Please choose one."
    : "";

  const needsResubmission =
    result?.success && ["NEEDS_RESUBMISSION", "FAILED"].includes(result.outcome);
  const resultClass = result?.success && !needsResubmission ? "success" : "error";

  let body;
  if (phase === "done") {
    body = (
      <div className="form-message success" role="status">
        Confirmed. Your account is now active. <a href="#home">Go to home</a>
      </div>
    );
  } else if (phase === "confirm") {
    body = (
      <>
        <div className="form-message" role="status">
          Your registration form passed screening. Review and correct anything below,
          then confirm to activate your account.
        </div>
        {confirmError && <div role="alert" className="form-message error">{confirmError}</div>}
        <form onSubmit={handleConfirm}>
          <ScreeningFields
            form={confirmForm}
            set={setConfirm}
            campuses={campuses}
            programs={programs}
            campusHint={campusHint}
            programHint={programHint}
            referenceError={referenceError}
            onRetryReference={() => void loadReference()}
          />
          <button type="submit" disabled={busy} className="btn-submit btn-success">
            {busy ? "Confirming…" : "Confirm details"}
          </button>
          <button type="button" onClick={handleReject} disabled={busy} className="btn-submit">
            Reject and re-upload
          </button>
        </form>
      </>
    );
  } else {
    body = (
      <>
        <form onSubmit={handleSubmit} encType="multipart/form-data">
          <div className="form-group full-width">
            <label className="form-group-label" htmlFor="register-email">Email</label>
            <input
              id="register-email"
              required
              type="email"
              className="form-input"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-group-label" htmlFor="register-password">Password (8+ characters)</label>
              <input
                id="register-password"
                required
                type="password"
                minLength={8}
                className="form-input"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-group-label" htmlFor="register-confirm">Confirm password</label>
              <input
                id="register-confirm"
                required
                type="password"
                minLength={8}
                className="form-input"
                value={form.confirm_password}
                onChange={(e) => set("confirm_password", e.target.value)}
              />
            </div>
          </div>

          <div className="upload-box">
            <div className="upload-title">Registration form (COR) — required PDF</div>
            <div className="upload-desc">
              Your Certificate of Registration is the required proof of current enrollment.
              PDF only, max 10 MB. Stored privately and deleted after your account is
              activated.
            </div>
            <input
              id="register-cor"
              required
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setCorFile(e.target.files?.[0] ?? null)}
              className="form-input"
            />
            {corFile && (
              <div className="form-hint">
                Attached: {corFile.name}
                {typeof corFile.size === "number" ? ` (${(corFile.size / 1024 / 1024).toFixed(2)} MB)` : ""}
              </div>
            )}
          </div>

          <button type="submit" disabled={submitting} className="btn-submit btn-success">
            {submitting ? "Submitting…" : "Submit registration"}
          </button>
        </form>

        {result && (
          <div className={`form-message ${resultClass}`} role="status">
            {result.message}
            {result.success && !result.canConfirm && (
              <> <a href="#registration">Continue</a></>
            )}
          </div>
        )}
      </>
    );
  }

  const card = (
    <div className="signup-card">
      {inModal && (
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
          <i className="fa-solid fa-xmark"></i>
        </button>
      )}

      <div className="signup-header">
        <h1>{phase === "confirm" || phase === "done" ? "Confirm your details" : "Create your account"}</h1>
        <p>
          Register with your email and password, then attach your current registration
          form (COR) — your proof of enrollment at the University of Caloocan City. We
          read the details from your COR and you confirm them to activate your account.
        </p>
      </div>

      {body}

      {phase === "form" && (inModal ? (
        <p className="signup-text">
          Already have an account? <button type="button" className="linklike" onClick={onSwitchToLogin}>Sign in</button>
        </p>
      ) : (
        <p className="footer-link" style={{ textAlign: "center" }}>
          <a href="#login">Already have an account? Sign in</a>
        </p>
      ))}
    </div>
  );

  return inModal ? card : <main className="auth-shell">{card}</main>;
}
