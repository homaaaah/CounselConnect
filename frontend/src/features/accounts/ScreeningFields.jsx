/**
 * ScreeningFields — summary of the COR-extracted academic fields, shared by the
 * Registration Status page and the inline confirm step.
 *
 * Every field states whether it can be edited: a lock chip marks values read
 * from the COR (student number, academic year, and a COR-matched campus/program)
 * and a pencil chip marks the values a Student may request to change (names,
 * year level, section, and an unmapped campus/program selection). The parent
 * supplies the wrapping <form> and the action buttons.
 */
export const YEAR_LEVELS = [1, 2, 3, 4, 5, 6];

function isSet(value) {
  return value !== "" && value !== null && value !== undefined;
}

function Chip({ editable }) {
  return editable ? (
    <span className="field-chip field-chip--editable">
      <i className="fa-solid fa-pen" aria-hidden="true" /> Editable
    </span>
  ) : (
    <span className="field-chip field-chip--locked">
      <i className="fa-solid fa-lock" aria-hidden="true" /> Read-only
    </span>
  );
}

function Locked({ id, label, value, hint }) {
  return (
    <div className="form-group">
      <label className="form-group-label" htmlFor={id}>
        {label}
        <Chip editable={false} />
      </label>
      <input
        id={id}
        readOnly
        aria-readonly="true"
        tabIndex={-1}
        className="form-input input-locked"
        value={value ?? ""}
        onChange={() => {}}
      />
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  );
}

function Editable({ id, label, value, onChange, hint }) {
  return (
    <div className="form-group">
      <label className="form-group-label" htmlFor={id}>
        {label}
        <Chip editable />
      </label>
      <input
        id={id}
        className="form-input"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint && <div className="form-hint">{hint}</div>}
    </div>
  );
}

export default function ScreeningFields({
  form,
  set,
  campuses,
  programs,
  campusHint,
  programHint,
  referenceError,
  onRetryReference,
  editable = false,
}) {
  const campusMatched = isSet(form.campus_id);
  const programMatched = isSet(form.program_id);
  const campus = campuses.find((c) => String(c.campus_id) === String(form.campus_id));
  const program = programs.find((p) => String(p.program_id) === String(form.program_id));

  return (
    <>
      {referenceError && (
        <div role="alert" className="form-message error">
          {referenceError}{" "}
          <button type="button" className="linklike" onClick={onRetryReference}>
            Retry options
          </button>
        </div>
      )}

      <p className="field-legend">
        {editable
          ? "Fields marked \u{1F512} Read-only were read from your COR and cannot be changed. Fields marked \u270E Editable you can change; those changes are reviewed by a Superadmin."
          : "Every field is marked \u{1F512} Read-only: these details were read from your COR and cannot be changed here."}
      </p>

      <div className="form-row">
        <Locked
          id="confirm-student-number"
          label="Student number"
          value={form.student_number}
          hint="Read from the barcode on your COR — cannot be changed."
        />
        <Locked
          id="confirm-academic-period"
          label="Academic year (optional)"
          value={form.academic_period}
          hint="Taken from your COR — cannot be changed."
        />
      </div>

      <div className="form-row">
        {editable ? (
          <Editable id="confirm-first-name" label="First name" value={form.first_name} onChange={(v) => set("first_name", v)} />
        ) : (
          <Locked id="confirm-first-name" label="First name" value={form.first_name} />
        )}
        {editable ? (
          <Editable id="confirm-last-name" label="Last name" value={form.last_name} onChange={(v) => set("last_name", v)} />
        ) : (
          <Locked id="confirm-last-name" label="Last name" value={form.last_name} />
        )}
      </div>

      <div className="form-group full-width">
        {editable ? (
          <Editable id="confirm-middle-name" label="Middle name (optional)" value={form.middle_name} onChange={(v) => set("middle_name", v)} />
        ) : (
          <Locked id="confirm-middle-name" label="Middle name (optional)" value={form.middle_name} />
        )}
      </div>

      <div className="form-row">
        {campusMatched ? (
          <Locked id="confirm-campus" label="Campus" value={campus?.campus_name ?? ""} />
        ) : (
          <div className="form-group">
            <label className="form-group-label" htmlFor="confirm-campus">
              Campus
              <Chip editable />
            </label>
            <select
              id="confirm-campus"
              required
              className="form-select"
              value={form.campus_id}
              onChange={(e) => set("campus_id", e.target.value)}
            >
              <option value="" disabled>Select campus</option>
              {campuses.map((c) => (
                <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>
              ))}
            </select>
            {campusHint && <div className="form-hint">{campusHint}</div>}
          </div>
        )}
        {programMatched ? (
          <Locked id="confirm-program" label="Program" value={program?.program_name ?? ""} />
        ) : (
          <div className="form-group">
            <label className="form-group-label" htmlFor="confirm-program">
              Program
              <Chip editable />
            </label>
            <select
              id="confirm-program"
              required
              className="form-select"
              value={form.program_id}
              onChange={(e) => set("program_id", e.target.value)}
            >
              <option value="" disabled>Select program</option>
              {programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>{p.program_name}</option>
              ))}
            </select>
            {programHint && <div className="form-hint">{programHint}</div>}
          </div>
        )}
      </div>

      <div className="form-row">
        {editable ? (
          <div className="form-group">
            <label className="form-group-label" htmlFor="confirm-year-level">
              Year level
              <Chip editable />
            </label>
            <select
              id="confirm-year-level"
              className="form-select"
              value={form.year_level}
              onChange={(event) => set("year_level", event.target.value)}
            >
              <option value="" disabled>Select year level</option>
              {YEAR_LEVELS.map((year) => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
        ) : (
          <Locked id="confirm-year-level" label="Year level" value={form.year_level} />
        )}
        {editable ? (
          <Editable id="confirm-section" label="Section" value={form.section} onChange={(v) => set("section", v)} />
        ) : (
          <Locked id="confirm-section" label="Section" value={form.section} />
        )}
      </div>
    </>
  );
}
