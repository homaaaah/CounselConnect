import { useState } from "react";
import { useRegistration, EMPTY_FORM } from "../features/accounts";

/**
 * Student registration (DFD 1.1 + 1.2): details + COR PDF, ONE submit.
 * Capstone card styling. inModal renders the same card without the
 * full-page shell, with an in-modal sign-in switch (landing overlay).
 */
export default function RegisterPage({ inModal = false, onClose, onSwitchToLogin }) {
  const { campuses, programs, register, submitting, referenceLoading, referenceError, retryReferenceData } = useRegistration();
  const [form, setForm] = useState(EMPTY_FORM);
  const [corFile, setCorFile] = useState(null);
  const [result, setResult] = useState(null);

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setResult(await register(form, corFile));
  }

  const card = (
    <div className="signup-card">
      {inModal && (
        <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
          <i className="fa-solid fa-xmark"></i>
        </button>
      )}

      <div className="signup-header">
        <h1>Create your account</h1>
        <p>
          Register with your details and attach your current registration form (COR) —
          your proof of enrollment at the University of Caloocan City. Everything is
          submitted together for Guidance Counselor approval.
        </p>
      </div>

      <form onSubmit={handleSubmit} encType="multipart/form-data">
        {referenceLoading && <p role="status" className="form-hint">Loading campus and program options...</p>}
        {referenceError && <div role="alert" className="form-message error">
          {referenceError} <button type="button" className="linklike" onClick={retryReferenceData}>Retry options</button>
        </div>}
        <div className="form-row">
          <div className="form-group">
            <label className="form-group-label">First name</label>
            <input required className="form-input" value={form.first_name}
              onChange={(e) => set("first_name", e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-group-label">Last name</label>
            <input required className="form-input" value={form.last_name}
              onChange={(e) => set("last_name", e.target.value)} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-group-label">Middle name (optional)</label>
            <input className="form-input" value={form.middle_name}
              onChange={(e) => set("middle_name", e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-group-label">Student number</label>
            <input required className="form-input" placeholder="e.g. 2026-00001"
              value={form.student_number}
              onChange={(e) => set("student_number", e.target.value)} />
          </div>
        </div>

        <div className="form-group full-width">
          <label className="form-group-label">Email</label>
          <input required type="email" className="form-input" value={form.email}
            onChange={(e) => set("email", e.target.value)} />
        </div>

        <div className="form-group full-width">
          <label className="form-group-label">Password (8+ characters)</label>
          <input required type="password" minLength={8} className="form-input"
            value={form.password} onChange={(e) => set("password", e.target.value)} />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-group-label">Campus</label>
            <select required className="form-select" value={form.campus_id}
              onChange={(e) => set("campus_id", e.target.value)}>
              <option value="" disabled>Select campus</option>
              {campuses.map((c) => (
                <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-group-label">Program</label>
            <select required className="form-select" value={form.program_id}
              onChange={(e) => set("program_id", e.target.value)}>
              <option value="" disabled>Select program</option>
              {programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>{p.program_name}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-group-label">Year level</label>
            <select required className="form-select" value={form.year_level}
              onChange={(e) => set("year_level", e.target.value)}>
              {[1, 2, 3, 4, 5, 6].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-group-label">Section</label>
            <input required maxLength={50} className="form-input" value={form.section}
              onChange={(e) => set("section", e.target.value)} />
          </div>
        </div>

        <div className="upload-box">
          <div className="upload-title">Registration form (COR) — required PDF</div>
          <div className="upload-desc">
            Your Certificate of Registration is the required proof of current enrollment.
            PDF only, max 10 MB. Stored privately and deleted after the decision.
          </div>
          <input
            required
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setCorFile(e.target.files?.[0] ?? null)}
            className="form-input"
          />
          {corFile && (
            <div className="form-hint">
              Attached: {corFile.name} ({(corFile.size / 1024 / 1024).toFixed(2)} MB)
            </div>
          )}
        </div>

        <button type="submit" disabled={submitting} className="btn-submit btn-success">
          {submitting ? "Submitting…" : "Submit registration for approval"}
        </button>
      </form>

      {result && (
        <div className={`form-message ${result.success ? "success" : "error"}`} role="status">
          {result.message}
        </div>
      )}

      {inModal ? (
        <p className="signup-text">
          Already have an account? <button type="button" className="linklike" onClick={onSwitchToLogin}>Sign in</button>
        </p>
      ) : (
        <p className="footer-link" style={{ textAlign: "center" }}>
          <a href="#landing">Back to landing page</a>
        </p>
      )}
    </div>
  );

  return inModal ? card : <main className="auth-shell">{card}</main>;
}
