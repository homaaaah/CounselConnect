/**
 * ScreeningFields — read-only summary of the COR-extracted academic fields
 * (shared by the Registration Status page and the inline confirm step).
 *
 * Verified fields are read-only: the Student must not rewrite them, they must
 * match what the COR/barcode yielded. The only values the Student may supply
 * are campus/program the COR could not be mapped to, which render as selects.
 * The parent supplies the wrapping <form> and the Confirm/Reject buttons.
 */
export const YEAR_LEVELS = [1, 2, 3, 4, 5, 6];

function isSet(value) {
  return value !== "" && value !== null && value !== undefined;
}

function Locked({ id, label, value, hint }) {
  return (
    <div className="form-group">
      <label className="form-group-label" htmlFor={id}>{label}</label>
      <input
        id={id}
        readOnly
        aria-readonly="true"
        tabIndex={-1}
        className="form-input bg-slate-100 text-slate-700"
        value={value ?? ""}
        onChange={() => {}}
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

      <p className="form-hint">
        These details were read from your COR and cannot be edited here. If anything
        is wrong, reject and upload a clearer or corrected COR.
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
        <Locked id="confirm-first-name" label="First name" value={form.first_name} />
        <Locked id="confirm-last-name" label="Last name" value={form.last_name} />
      </div>

      <div className="form-group full-width">
        <Locked id="confirm-middle-name" label="Middle name (optional)" value={form.middle_name} />
      </div>

      <div className="form-row">
        {campusMatched ? (
          <Locked id="confirm-campus" label="Campus" value={campus?.campus_name ?? ""} />
        ) : (
          <div className="form-group">
            <label className="form-group-label" htmlFor="confirm-campus">Campus</label>
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
            <label className="form-group-label" htmlFor="confirm-program">Program</label>
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
        <Locked id="confirm-year-level" label="Year level" value={form.year_level} />
        <Locked id="confirm-section" label="Section" value={form.section} />
      </div>
    </>
  );
}
