import { useEffect, useState } from "react";
import { formatSchedule, manilaToday } from "../../features/appointments";
import { buttonClass, modeLabel } from "./ui.js";
import CalendarGrid from "./CalendarGrid.jsx";

/**
 * BookingModal — the Schedule flow in a dialog: calendar → pick a date →
 * revealed slot details (campus, time, counselor, mode) → request.
 * Booking calls POST /appointments (owner Student); reschedule calls
 * POST /appointments/{id}/reschedule (owner Student/assigned Counselor).
 *
 * Data flow: picking a date seeds the hook's date filter (starts_after/
 * ends_before on GET /availability-slots) so the slots list covers that
 * day; the picked calendar time (Manila "HH:MM") is then matched to a
 * slot by epoch instant (slot starts_at is UTC ISO — string equality
 * would never hit). state.mutate returns a boolean and surfaces its own
 * message/error, so success shows a confirmation panel here and failure
 * keeps the details visible with the error beside them.
 *
 * Layout (redesign): a fixed header (title, live step subtitle, PROGRESS
 * bar), a scrollable body with a two-panel grid (availability calendar on
 * the left, appointment details on the right), and a fixed footer
 * (Back / Cancel + the primary confirm action). The card itself is the
 * <form>, so the footer's confirm button submits the same handler as before.
 *
 * Real steps: the app has no counselor-first or six-step wizard — booking is
 * slot-scoped and GET /availability-slots is the only counselor/campus
 * source. The progress therefore reflects the two real stages of this dialog:
 * 1) choose date & time, 2) confirm details.
 */
export default function BookingModal({ open, onClose, state, rescheduleId = null }) {
  const [selectedDate, setSelectedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [slotCandidates, setSlotCandidates] = useState([]);
  const [selectedSlotId, setSelectedSlotId] = useState(null);
  const [slotDetails, setSlotDetails] = useState(null);
  const [mode, setMode] = useState("ONLINE");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const resetSelection = () => {
    setSelectedDate(null); setPickedTime(null); setSlotCandidates([]); setSelectedSlotId(null); setSlotDetails(null);
    setMode("ONLINE"); setDone(false);
  };

  useEffect(() => { if (!open) resetSelection(); }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Picking a date loads that day's slots through the hook's date filter.
  useEffect(() => {
    if (!open || !selectedDate) return;
    if (state.date !== selectedDate) state.setDate(selectedDate);
    if (state.slotPage !== 1) state.setSlotPage(1);
  }, [open, selectedDate, state.date, state.slotPage, state.setDate, state.setSlotPage]);

  // Match the picked time to every loaded slot once that date's slots arrive.
  // A calendar start is intentionally distinct from a concrete slot: several
  // counselors or campuses may be available at that same Manila time.
  useEffect(() => {
    if (!open || !selectedDate || !pickedTime || state.loading) return;
    const startEpoch = new Date(selectedDate + "T" + pickedTime + ":00+08:00").getTime();
    const matches = state.slots.items.filter(s => new Date(s.starts_at).getTime() === startEpoch);
    setSlotCandidates(matches);
    setSelectedSlotId((current) => matches.some((slot) => slot.slot_id === current)
      ? current : (matches[0]?.slot_id ?? null));
  }, [open, selectedDate, pickedTime, state.loading, state.slots]);

  useEffect(() => {
    const selected = slotCandidates.find((slot) => slot.slot_id === selectedSlotId) ?? null;
    setSlotDetails(selected);
    if (selected?.delivery_mode === "FACE_TO_FACE") setMode("FACE_TO_FACE");
    if (selected?.delivery_mode === "ONLINE") setMode("ONLINE");
  }, [slotCandidates, selectedSlotId]);

  const submit = async (event) => {
    event.preventDefault();
    if (!slotDetails || submitting) return;
    setSubmitting(true);
    const path = rescheduleId ? "/appointments/" + rescheduleId + "/reschedule" : "/appointments";
    const ok = await state.mutate(path,
      { availability_slot_id: slotDetails.slot_id, appointment_mode: mode }, "POST",
      rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review.");
    setSubmitting(false);
    if (ok) {
      setDone(true);
    }
    // On failure state.mutate surfaces state.error beside the details; the
    // details stay visible so the visitor can change time or retry (the
    // server rejects stale slots again with SLOT_UNAVAILABLE).
  };

  if (!open) return null;

  const today = manilaToday();
  const stepTotal = 2;
  const step = slotDetails ? 2 : 1;
  const progressPercent = Math.round((step / stepTotal) * 100);
  const subtitle = rescheduleId
    ? (step === 1 ? "Step 1 of 2: Choose a new date & time" : "Step 2 of 2: Confirm reschedule")
    : (step === 1 ? "Step 1 of 2: Choose date & time" : "Step 2 of 2: Confirm your appointment");
  const onCalendarSelect = () => {
    setPickedTime(null); setSlotCandidates([]); setSelectedSlotId(null); setSlotDetails(null); setMode("ONLINE");
  };
  const onCalendarPickTime = (date, time) => {
    setSelectedDate(date); setPickedTime(time); setSlotCandidates([]); setSelectedSlotId(null); setSlotDetails(null); setMode("ONLINE");
  };
  const confirmDisabled = submitting || state.busy || !slotDetails
    || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location);

  return <div className="modal-overlay" role="dialog" aria-modal="true"
    aria-label={rescheduleId ? "Reschedule appointment" : "Schedule an appointment"}
    onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
    <form className="modal-card booking-modal-card" onSubmit={submit}>
      <button type="button" className="modal-close booking-modal-close" onClick={onClose} aria-label="Close dialog">
        <i className="fa-solid fa-xmark" aria-hidden="true"></i>
      </button>

      <header className="booking-modal-header">
        <h2 className="booking-modal-title">{rescheduleId ? "Reschedule appointment" : "Schedule an Appointment"}</h2>
        <p className="booking-modal-subtitle">{subtitle}</p>
        <div className="booking-progress-row">
          <span className="booking-progress-label">Progress</span>
          <span className="booking-progress-label">Step {step} of {stepTotal}</span>
        </div>
        <div className="booking-progress-track" role="progressbar" aria-label="Booking progress"
          aria-valuemin={0} aria-valuemax={stepTotal} aria-valuenow={step}>
          <div className="booking-progress-fill" style={{ width: progressPercent + "%" }} />
        </div>
      </header>

      <div className="booking-modal-body">
        {done
          ? <div className="booking-success">
              <h3 className="booking-success-title">{rescheduleId ? "Reschedule requested" : "Appointment requested"}</h3>
              <p role="status" className="booking-success-note">
                {rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review."}
              </p>
            </div>
          : (!state.calendar && state.loading)
            ? <p role="status" className="booking-loading">Loading calendar...</p>
            : <div className="booking-layout">
                <section className="booking-panel booking-panel--calendar" aria-label="Availability calendar">
                  <CalendarGrid variant="modal" calendar={state.calendar}
                    onSelect={onCalendarSelect} onPickTime={onCalendarPickTime} />
                  <div className="booking-legend">
                    <span className="booking-legend-item"><span className="booking-dot booking-dot--selected" aria-hidden="true" />Selected</span>
                    <span className="booking-legend-item"><span className="booking-dot booking-dot--available" aria-hidden="true" />Available</span>
                    <span className="booking-legend-item"><span className="booking-dot booking-dot--unavailable" aria-hidden="true" />Unavailable</span>
                  </div>
                </section>

                <section className="booking-panel booking-panel--details" aria-label="Appointment details">
                  {state.error && <div role="alert" className="booking-alert booking-alert--error">
                    <p>{state.error}</p>
                    <button type="button" className="booking-btn-text" disabled={state.loading}
                      onClick={() => void state.refresh?.()}>
                      {state.loading ? "Retrying availability…" : "Retry availability"}
                    </button>
                  </div>}

                  {!pickedTime && <p className="booking-hint">Click a date to see available times, then pick one to reveal campus and mode details. Philippine time.</p>}
                  {selectedDate && !pickedTime && <p className="booking-hint">Pick a time on your selected date to continue.</p>}
                  {pickedTime && state.loading && <p role="status" className="booking-hint">Loading slot details...</p>}
                  {pickedTime && !state.loading && !slotDetails &&
                    <p role="alert" className="booking-alert booking-alert--warn">That time is no longer available. Please pick another time.</p>}

                  {pickedTime && !state.loading && slotDetails && <div className="booking-details">
                    <h3 className="booking-details-title">Additional information</h3>

                    {slotCandidates.length > 0 && <fieldset className="booking-counselors">
                      <legend className="booking-counselors-legend">Choose an available counselor and campus</legend>
                      <div className="booking-counselors-grid">
                        {slotCandidates.map((candidate) => <button key={candidate.slot_id} type="button"
                          aria-pressed={selectedSlotId === candidate.slot_id}
                          aria-label={`Choose ${candidate.counselor_name} at ${candidate.campus_name}`}
                          className={"booking-counselor-card" + (selectedSlotId === candidate.slot_id ? " booking-counselor-card--selected" : "")}
                          onClick={() => setSelectedSlotId(candidate.slot_id)}>
                          <span className="booking-availability">
                            <span className={"booking-dot " + (selectedDate === today ? "booking-dot--available" : "booking-dot--soon")} aria-hidden="true" />
                            {selectedDate === today ? "Available today" : "Available"}
                          </span>
                          <span className="booking-counselor-name">{candidate.counselor_name}</span>
                          <span className="booking-counselor-campus">{candidate.campus_name} · {modeLabel(candidate.delivery_mode)}</span>
                          {selectedSlotId === candidate.slot_id && <span className="booking-counselor-check" aria-hidden="true"><i className="fa-solid fa-check"></i></span>}
                        </button>)}
                      </div>
                    </fieldset>}

                    <dl className="booking-info">
                      <div><dt>Campus</dt><dd>{slotDetails.campus_name}</dd></div>
                      <div><dt>Time</dt><dd>{formatSchedule(slotDetails.starts_at)} – {formatSchedule(slotDetails.ends_at)}</dd></div>
                      <div><dt>Counselor</dt><dd>{slotDetails.counselor_name}</dd></div>
                      <div><dt>Mode</dt><dd>{modeLabel(slotDetails.delivery_mode)}</dd></div>
                      {slotDetails.guidance_office_location && <div className="booking-info-wide"><dt>Guidance Office</dt><dd>{slotDetails.guidance_office_location}</dd></div>}
                    </dl>

                    <label className="booking-field">Appointment mode
                      <select className="booking-select" value={mode} onChange={e => setMode(e.target.value)}>
                        {slotDetails.delivery_mode !== "FACE_TO_FACE" && <option value="ONLINE">Online</option>}
                        {slotDetails.delivery_mode !== "ONLINE" && <option value="FACE_TO_FACE">Face-to-face</option>}
                      </select>
                    </label>

                    {slotDetails.delivery_mode !== "ONLINE" && !slotDetails.guidance_office_location && (
                      <p role="alert" className="booking-alert booking-alert--warn">This campus has no Guidance Office location yet; face-to-face booking is unavailable for this slot.</p>
                    )}
                  </div>}
                </section>
              </div>}
      </div>

      <footer className="booking-modal-footer">
        {done
          ? <button type="button" className={buttonClass + " booking-btn-primary"} onClick={onClose}>Close</button>
          : <>
              <div className="booking-footer-left">
                {slotDetails && <button type="button" className="booking-btn-text" disabled={state.busy}
                  onClick={() => { setPickedTime(null); setSlotDetails(null); }}>‹ Back</button>}
                <button type="button" className="booking-btn-text" onClick={onClose}>Cancel</button>
              </div>
              <button type="submit" className={buttonClass + " booking-btn-primary"} disabled={confirmDisabled}>
                {rescheduleId ? "Confirm reschedule" : "Confirm booking"}
              </button>
            </>}
      </footer>
    </form>
  </div>;
}
