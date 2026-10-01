import { useEffect, useState } from "react";
import {
  useRegistration,
  EMPTY_FORM,
  confirmedFieldsFrom,
  actionErrorMessage,
  failureReasonText,
  editedEditableFields,
  ScreeningFields,
} from "../features/accounts";
import { request } from "../services/apiClient";

/**
 * Student registration (automated COR screening): one card with email +
 * password + COR. Registration does NOT sign the student in; the response's
 * one-time verification token (kept only in component memory) authorizes the
 * inline confirm / reject / re-upload steps so activation happens without a
 * session. inModal renders the same card without the full-page shell.
 */
export default function RegisterPage({ inModal = false, onClose, onSwitchToLogin }) {
  const { register, submitting } = useRegistration();
  const [form, setForm] = useState(EMPTY_FORM);
  const [corFile, setCorFile] = useState(null);
  const [result, setResult] = useState(null);
  const [verificationToken, setVerificationToken] = useState(null);

  const [phase, setPhase] = useState("form"); // "form" | "confirm" | "resubmit" | "done"
  const [screening, setScreening] = useState(null);
  const [unmatched, setUnmatched] = useState({ campus: null, program: null });
  const [confirmForm, setConfirmForm] = useState(null);
  const [campuses, setCampuses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [referenceError, setReferenceError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [resubmitFile, setResubmitFile] = useState(null);
  const [resubmitError, setResubmitError] = useState("");
  const [pendingEdit, setPendingEdit] = useState(false);

  // The one-time token header authorizes the modal actions. Omit it entirely
  // when absent (never send an empty credential); the backend fails closed.
  const tokenHeaders = verificationToken ? { "X-COR-Token": verificationToken } : {};

  // Editable fields (names/year_level/section) that differ from the COR.
  const editDiffs = phase === "confirm" ? editedEditableFields(screening, confirmForm) : [];
  const hasEdits = editDiffs.length > 0;

  function confirmPayload() {
    return {
      student_number: confirmForm.student_number.trim(),
      first_name: confirmForm.first_name.trim(),
      middle_name: (confirmForm.middle_name ?? "").trim() || null,
      last_name: confirmForm.last_name.trim(),
      campus_id: Number(confirmForm.campus_id),
      program_id: Number(confirmForm.program_id),
      year_level: Number(confirmForm.year_level),
      section: confirmForm.section.trim(),
      academic_period: (confirmForm.academic_period ?? "").trim() || null,
    };
  }

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
      setVerificationToken(r.verificationToken ?? null);
      if (r.canConfirm) {
        setScreening(r.screening);
        setConfirmForm(confirmedFieldsFrom(r.screening));
        setUnmatched({ campus: r.unmatched_campus_name, program: r.unmatched_program_name });
        setConfirmError("");
        setPhase("confirm");
      } else if (["NEEDS_RESUBMISSION", "FAILED"].includes(r.outcome)) {
        // Keep the flow in this same card: offer a re-upload instead of a link out.
        setScreening(r.screening);
        setResubmitFile(null);
        setResubmitError("");
        setPhase("resubmit");
      }
    }
  }

  function confirmMissing() {
    return !confirmForm.student_number || !confirmForm.first_name || !confirmForm.last_name
      || confirmForm.campus_id === "" || confirmForm.program_id === ""
      || confirmForm.year_level === "" || !confirmForm.section;
  }

  async function handleConfirm(e) {
    e.preventDefault();
    if (confirmMissing()) {
      setConfirmError("Please complete every required field before confirming.");
      return;
    }
    if (hasEdits) {
      await handleRequestEdit();
      return;
    }
    setBusy(true);
    setConfirmError("");
    try {
      await request("/cor-screenings/confirm", {
        method: "POST",
        headers: tokenHeaders,
        body: JSON.stringify(confirmPayload()),
      });
      setPhase("done");
    } catch (err) {
      setConfirmError(actionErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRequestEdit() {
    if (confirmMissing()) {
      setConfirmError("Please complete every required field.");
      return;
    }
    setBusy(true);
    setConfirmError("");
    try {
      const response = await request("/cor-screenings/request-edit", {
        method: "POST",
        headers: tokenHeaders,
        body: JSON.stringify(confirmPayload()),
      });
      setScreening(response?.screening ?? screening);
      setPendingEdit(Boolean(response?.change_request));
      setPhase("done");
    } catch (err) {
      setConfirmError(actionErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRejectAccount() {
    const confirmed = typeof window === "undefined" || typeof window.confirm !== "function"
      ? true
      : window.confirm("Reject this registration? Your account and uploaded COR will be deleted.");
    if (!confirmed) {
      return;
    }
    setBusy(true);
    setConfirmError("");
    setResubmitError("");
    try {
      await request("/cor-screenings/reject-account", {
        method: "POST",
        headers: tokenHeaders,
      });
      setVerificationToken(null);
      setPhase("cancelled");
    } catch (err) {
      const text = actionErrorMessage(err);
      setConfirmError(text);
      setResubmitError(text);
    } finally {
      setBusy(false);
    }
  }

  async function handleResubmit(e) {
    e.preventDefault();
    if (!resubmitFile) {
      setResubmitError("Please choose your registration form (COR) PDF.");
      return;
    }
    setBusy(true);
    setResubmitError("");
    try {
      const body = new FormData();
      body.append("file", resubmitFile);
      const response = await request("/cor-screenings/resubmit", {
        method: "POST",
        headers: tokenHeaders,
        body,
      });
      const next = response?.screening ?? null;
      setScreening(next);
      // Re-upload rotates the one-time token; keep the latest one in memory.
      if (response?.verification_token) setVerificationToken(response.verification_token);
      if (next?.status === "AWAITING_CONFIRMATION") {
        setConfirmForm(confirmedFieldsFrom(next));
        setUnmatched({ campus: null, program: null });
        setConfirmError("");
        setPhase("confirm");
      } else {
        setResubmitFile(null);
        setResubmitError(
          next?.failure_reason_code
            ? failureReasonText(next.failure_reason_code)
            : "We still could not read your COR. Please upload a clearer copy.",
        );
      }
    } catch (err) {
      setResubmitError(actionErrorMessage(err));
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
        {pendingEdit
          ? "Account activated. Your requested changes are pending Superadmin approval."
          : "Account activated. You can now sign in with your email or student number."}
        {inModal ? (
          <> <button type="button" className="linklike" onClick={onSwitchToLogin}>Sign in</button></>
        ) : (
          <> <a href="#login">Sign in</a></>
        )}
      </div>
    );
  } else if (phase === "confirm") {
    body = (
      <>
        <div className="form-message" role="status">
          {hasEdits
            ? "You changed some details. Submit an edit request for Superadmin approval; your account activates now with the details printed on your COR."
            : "Your registration form passed screening. Review and correct anything below, then confirm to activate your account."}
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
            editable
          />
          <div className="form-actions">
            {hasEdits ? (
              <button type="button" onClick={handleRequestEdit} disabled={busy} className="btn-submit btn-success">
                {busy ? "Submitting…" : "Submit edit request"}
              </button>
            ) : (
              <button type="submit" disabled={busy} className="btn-submit btn-success">
                {busy ? "Confirming…" : "Confirm details"}
              </button>
            )}
            <button
              type="button"
              onClick={handleRejectAccount}
              disabled={busy}
              className="btn-submit btn-danger"
            >
              Reject account
            </button>
          </div>
        </form>
      </>
    );
  } else if (phase === "resubmit") {
    const reason = screening?.failure_reason_code
      ? failureReasonText(screening.failure_reason_code)
      : "We could not read all of your registration form.";
    body = (
      <>
        <div className="form-message error" role="alert">
          {reason} Re-upload a clearer or corrected copy of your COR to continue.
        </div>
        {resubmitError && <div role="alert" className="form-message error">{resubmitError}</div>}
        <form onSubmit={handleResubmit} encType="multipart/form-data">
          <div className="upload-box">
            <div className="upload-title">Registration form (COR) — re-upload</div>
            <div className="upload-desc">
              PDF only, max 10 MB. Stored privately and deleted after your account is activated.
            </div>
            <input
              id="resubmit-cor"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setResubmitFile(e.target.files?.[0] ?? null)}
              className="form-input"
            />
            {resubmitFile && <div className="form-hint">Attached: {resubmitFile.name}</div>}
          </div>
          <div className="form-actions">
            <button type="submit" disabled={busy || !resubmitFile} className="btn-submit btn-success">
              {busy ? "Uploading…" : "Upload COR"}
            </button>
            <button
              type="button"
              onClick={handleRejectAccount}
              disabled={busy}
              className="btn-submit btn-danger"
            >
              Reject account
            </button>
          </div>
        </form>
      </>
    );
  } else if (phase === "cancelled") {
    body = (
      <div className="form-message error" role="status">
        Registration cancelled. Your account and uploaded COR were deleted.
        {inModal ? (
          <> <button type="button" className="linklike" onClick={onClose}>Close</button></>
        ) : (
          <> <a href="#home">Back to home</a></>
        )}
      </div>
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
          </div>
        )}
      </>
    );
  }

  const headers = {
    form: {
      title: "Create your account",
      subtitle:
        "Register with your email and password, then attach your current registration form (COR) — your proof of enrollment at the University of Caloocan City.",
    },
    confirm: {
      title: "Review your details",
      subtitle:
        "Check the details we read from your COR. Confirm to activate your account, or request an edit for Superadmin approval.",
    },
    resubmit: {
      title: "Re-upload your COR",
      subtitle:
        "We could not read your COR clearly. Upload a clearer or corrected PDF to continue.",
    },
    done: { title: "You're all set", subtitle: "" },
    cancelled: { title: "Registration cancelled", subtitle: "" },
  };
  const header = headers[phase] ?? headers.form;

  const card = (
    <div className="signup-card">
      {inModal && (
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
          <i className="fa-solid fa-xmark"></i>
        </button>
      )}

      <div className="signup-header">
        <h1>{header.title}</h1>
        {header.subtitle && <p>{header.subtitle}</p>}
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
