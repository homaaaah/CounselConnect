import { useEffect, useState } from "react";
import { formatSchedule, manilaToday } from "../../features/appointments";
import { buttonClass, modeLabel } from "./ui.js";
import CalendarGrid from "./CalendarGrid.jsx";

const STEP_LABELS = ["Counselor", "Date", "Time", "Session mode", "Review", "Submit"];

/** Guided counselor-first booking flow. The existing appointment mutation remains authoritative. */
export default function BookingModal({ open, onClose, state, rescheduleId = null }) {
  const [step, setStep] = useState(1);
  const [selectedCounselorId, setSelectedCounselorId] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [slotCandidates, setSlotCandidates] = useState([]);
  const [selectedSlotId, setSelectedSlotId] = useState(null);
  const [slotSelectionInitialized, setSlotSelectionInitialized] = useState(false);
  const [slotDetails, setSlotDetails] = useState(null);
  const [mode, setMode] = useState("ONLINE");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const resetSelection = () => {
    setStep(1); setSelectedCounselorId(null); setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setDone(false);
    state.setCounselorUserId?.("");
  };
  useEffect(() => { if (!open) resetSelection(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onKey = event => { if (event.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  useEffect(() => {
    if (!open || !selectedDate) return;
    if (state.date !== selectedDate) state.setDate(selectedDate);
    if (state.slotPage !== 1) state.setSlotPage(1);
  }, [open, selectedDate, state.date, state.slotPage, state.setDate, state.setSlotPage]);
  useEffect(() => {
    if (!open || !selectedDate || !pickedTime || state.loading) return;
    const startEpoch = new Date(`${selectedDate}T${pickedTime}:00+08:00`).getTime();
    const matches = state.slots.items.filter(slot =>
      slot.counselor_user_id === selectedCounselorId
      && new Date(slot.starts_at).getTime() === startEpoch);
    setSlotCandidates(matches);
    if (matches.some(slot => slot.slot_id === selectedSlotId)) return;
    if (!slotSelectionInitialized && matches.length > 0) {
      setSlotSelectionInitialized(true);
      setSelectedSlotId(matches[0].slot_id);
    } else {
      setSelectedSlotId(null);
    }
  }, [open, selectedDate, pickedTime, state.loading, state.slots, selectedCounselorId, selectedSlotId, slotSelectionInitialized]);
  useEffect(() => {
    const selected = slotCandidates.find(slot => slot.slot_id === selectedSlotId) ?? null;
    setSlotDetails(selected);
    if (selected?.delivery_mode === "FACE_TO_FACE") setMode("FACE_TO_FACE");
    if (selected?.delivery_mode === "ONLINE") setMode("ONLINE");
  }, [slotCandidates, selectedSlotId]);

  const chooseCounselor = counselor => {
    setSelectedCounselorId(counselor.counselor_user_id);
    state.setCounselorUserId?.(String(counselor.counselor_user_id));
    state.setDate(""); setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(2);
  };
  const onCalendarSelect = date => {
    setSelectedDate(date); setPickedTime(null); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(3);
  };
  const onCalendarPickTime = (date, time) => {
    setSelectedDate(date); setPickedTime(time); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(3);
  };
  const onCalendarMonthChange = month => {
    state.setCalendarMonth?.(month); state.setDate?.("");
    setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(2);
  };
  const back = () => {
    if (step === 5) setStep(4);
    else if (step === 4) setStep(3);
    else if (step === 3) setStep(2);
    else if (step === 2) {
      state.setCounselorUserId?.(""); setSelectedCounselorId(null); state.setDate("");
      setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
      setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(1);
    }
  };
  const submit = async event => {
    event.preventDefault();
    if (!slotDetails || submitting || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location)) return;
    setStep(6); setSubmitting(true);
    const path = rescheduleId ? `/appointments/${rescheduleId}/reschedule` : "/appointments";
    const ok = await state.mutate(path,
      { availability_slot_id: slotDetails.slot_id, appointment_mode: mode }, "POST",
      rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review.");
    setSubmitting(false);
    if (ok) setDone(true);
    else setStep(5);
  };
  if (!open) return null;

  const stepTotal = STEP_LABELS.length;
  const progressPercent = Math.round((step / stepTotal) * 100);
  const subtitle = done ? "Request submitted" : `Step ${step} of ${stepTotal}: ${STEP_LABELS[step - 1]}`;
  const confirmDisabled = submitting || state.busy || !slotDetails
    || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location);
  const today = manilaToday();
  const availableModes = slotDetails?.delivery_mode === "BOTH" ? ["ONLINE", "FACE_TO_FACE"]
    : slotDetails ? [slotDetails.delivery_mode] : [];

  return <div className="modal-overlay" role="dialog" aria-modal="true"
    aria-label={rescheduleId ? "Reschedule appointment" : "Schedule an appointment"}
    onClick={event => { if (event.target === event.currentTarget) onClose?.(); }}>
    <form className="modal-card booking-modal-card" onSubmit={submit}>
      <button type="button" className="modal-close booking-modal-close" onClick={onClose} aria-label="Close dialog">
        <i className="fa-solid fa-xmark" aria-hidden="true"></i>
      </button>
      <header className="booking-modal-header">
        <h2 className="booking-modal-title">{rescheduleId ? "Reschedule appointment" : "Schedule an Appointment"}</h2>
        <p className="booking-modal-subtitle" aria-live="polite">{subtitle}</p>
        <div className="booking-progress-row"><span className="booking-progress-label">Booking progress</span>
          <span className="booking-progress-label">Step {step} of {stepTotal}</span></div>
        <div className="booking-progress-track" role="progressbar" aria-label="Booking progress"
          aria-valuemin={0} aria-valuemax={stepTotal} aria-valuenow={step}>
          <div className="booking-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
      </header>

      <div className="booking-modal-body">
        {done ? <div className="booking-success">
          <h3 className="booking-success-title">{rescheduleId ? "Reschedule requested" : "Appointment requested"}</h3>
          <p role="status" className="booking-success-note">Awaiting counselor review.</p>
        </div> : step === 6 && submitting ? <p role="status" className="booking-loading">Submitting your request…</p>
          : step === 1 ? <section className="booking-panel" aria-label="Choose a counselor">
            <h3 className="booking-details-title">Choose a Counselor</h3>
            {state.bookingCounselorsError && <div role="alert" className="booking-alert booking-alert--error">
              <p>{state.bookingCounselorsError}</p><button type="button" className="booking-btn-text" onClick={() => void state.refresh?.()}>Retry</button>
            </div>}
            {state.loading && state.bookingCounselors.length === 0
              ? <p role="status" className="booking-hint">Loading Counselors…</p>
              : state.bookingCounselors.length === 0
                ? <p className="booking-hint">No active Counselors are available right now.</p>
                : <div className="booking-counselors-grid">{state.bookingCounselors.map(counselor =>
                  <button type="button" key={counselor.counselor_user_id} className="booking-counselor-card"
                    onClick={() => chooseCounselor(counselor)}>
                    <span className="booking-counselor-name">{counselor.counselor_name}</span>
                    <span className="booking-counselor-campus">View available dates and times</span>
                  </button>)}</div>}
          </section> : step >= 2 && step <= 3 ? <div className="booking-layout">
            <section className="booking-panel booking-panel--calendar" aria-label="Availability calendar">
              <p className="booking-hint">Counselor: {state.bookingCounselors.find(item => item.counselor_user_id === selectedCounselorId)?.counselor_name}</p>
              <CalendarGrid variant="modal" calendar={state.calendar} month={state.calendarMonth}
                loading={state.loading} onRetry={state.refresh} onMonthChange={onCalendarMonthChange}
                onSelect={onCalendarSelect} onPickTime={onCalendarPickTime} />
              <div className="booking-legend">
                <span className="booking-legend-item"><span className="booking-dot booking-dot--selected" aria-hidden="true" />Selected</span>
                <span className="booking-legend-item"><span className="booking-dot booking-dot--available" aria-hidden="true" />Available</span>
                <span className="booking-legend-item"><span className="booking-dot booking-dot--unavailable" aria-hidden="true" />Unavailable</span>
              </div>
            </section>
            <section className="booking-panel booking-panel--details" aria-label="Choose an available time">
              {state.error && <div role="alert" className="booking-alert booking-alert--error"><p>{state.error}</p>
                <button type="button" className="booking-btn-text" disabled={state.loading} onClick={() => void state.refresh?.()}>
                  {state.loading ? "Retrying availability…" : "Retry availability"}</button></div>}
              {!selectedDate && <p className="booking-hint">Choose a date on the calendar.</p>}
              {selectedDate && !pickedTime && <p className="booking-hint">Choose one of the available times shown below the calendar.</p>}
              {pickedTime && state.loading && <p role="status" className="booking-hint">Checking this time…</p>}
              {pickedTime && !state.loading && slotCandidates.length === 0 && <p role="alert" className="booking-alert booking-alert--warn">That time is no longer available. Choose another time.</p>}
              {slotCandidates.length > 0 && <fieldset className="booking-counselors">
                <legend className="booking-counselors-legend">Choose the campus for {pickedTime}</legend>
                <div className="booking-counselors-grid">{slotCandidates.map(candidate => <button key={candidate.slot_id} type="button"
                  aria-pressed={selectedSlotId === candidate.slot_id}
                  aria-label={`Choose ${candidate.campus_name} at ${candidate.counselor_name}`}
                  className={`booking-counselor-card${selectedSlotId === candidate.slot_id ? " booking-counselor-card--selected" : ""}`}
                  onClick={() => { setSlotSelectionInitialized(true); setSelectedSlotId(candidate.slot_id); }}>
                  <span className="booking-availability"><span className={`booking-dot ${selectedDate === today ? "booking-dot--available" : "booking-dot--soon"}`} />Available</span>
                  <span className="booking-counselor-name">{candidate.campus_name}</span>
                  <span className="booking-counselor-campus">{modeLabel(candidate.delivery_mode)}</span>
                </button>)}</div>
              </fieldset>}
            </section>
          </div> : <section className="booking-panel" aria-label={step === 4 ? "Choose session mode" : "Review appointment"}>
            {slotDetails && <>
              {state.error && <div role="alert" className="booking-alert booking-alert--error">{state.error}</div>}
              <h3 className="booking-details-title">{step === 4 ? "Choose session mode" : "Review your appointment"}</h3>
              <dl className="booking-info">
                <div><dt>Counselor</dt><dd>{slotDetails.counselor_name}</dd></div>
                <div><dt>Campus</dt><dd>{slotDetails.campus_name}</dd></div>
                <div><dt>Date</dt><dd>{new Date(`${selectedDate}T00:00:00+08:00`).toLocaleDateString("en-PH", { timeZone: "Asia/Manila", dateStyle: "full" })}</dd></div>
                <div><dt>Time</dt><dd>{formatSchedule(slotDetails.starts_at)} – {formatSchedule(slotDetails.ends_at)}</dd></div>
                {step === 5 && <div><dt>Session mode</dt><dd>{modeLabel(mode)}</dd></div>}
                {mode === "FACE_TO_FACE" && slotDetails.guidance_office_location && <div className="booking-info-wide"><dt>Guidance Office</dt><dd>{slotDetails.guidance_office_location}</dd></div>}
              </dl>
              {step === 4 && <><label className="booking-field" htmlFor="booking-mode">Appointment mode
                <select id="booking-mode" className="booking-select" value={mode} onChange={event => setMode(event.target.value)}>
                  {availableModes.includes("ONLINE") && <option value="ONLINE">Online</option>}
                  {availableModes.includes("FACE_TO_FACE") && <option value="FACE_TO_FACE">Face-to-face</option>}
                </select></label>
                {availableModes.includes("FACE_TO_FACE") && !slotDetails.guidance_office_location && <p role="alert" className="booking-alert booking-alert--warn">Face-to-face booking is unavailable because this campus has no Guidance Office location.</p>}
              </>}
              {step === 5 && <p className="booking-hint">Submitting creates a pending appointment request. The Counselor will review it.</p>}
            </>}
            {!slotDetails && step >= 4 && pickedTime && !state.loading && <div role="alert" className="booking-alert booking-alert--warn">
              This selected slot is no longer available. Choose another time or campus.
              <button type="button" className="booking-btn-text" onClick={() => setStep(3)}>Change time or campus</button>
            </div>}
          </section>}
      </div>

      <footer className="booking-modal-footer">
        {done ? <button type="button" className={`${buttonClass} booking-btn-primary`} onClick={onClose}>Close</button> : <>
          <div className="booking-footer-left">
            {step > 1 && step < 6 && <button type="button" className="booking-btn-text" disabled={submitting || state.busy} onClick={back}>‹ Back</button>}
            <button type="button" className="booking-btn-text" onClick={onClose}>Cancel</button>
          </div>
          {step === 3 && <button type="button" className={`${buttonClass} booking-btn-primary`} disabled={!slotDetails || state.loading}
            onClick={() => setStep(4)}>Continue</button>}
          {step === 4 && <button type="button" className={`${buttonClass} booking-btn-primary`}
            onClick={() => setStep(5)} disabled={!slotDetails || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location)}>Review appointment</button>}
          {step === 5 && <button type="submit" className={`${buttonClass} booking-btn-primary`} disabled={confirmDisabled}>
            {rescheduleId ? "Submit reschedule" : "Submit request"}</button>}
        </>}
      </footer>
    </form>
  </div>;
}
