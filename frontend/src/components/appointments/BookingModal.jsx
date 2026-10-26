import { useEffect, useState } from "react";
import { formatSchedule, manilaToday } from "../../features/appointments";
import { buttonClass, modeLabel } from "./ui.js";
import CalendarGrid from "./CalendarGrid.jsx";
import ConcernSummary from "./ConcernSummary.jsx";
import {
  ALL_CONCERNS_VALUE,
  CUSTOM_CONCERN,
  STANDARD_CONCERNS,
  toggleConcernCategory,
} from "./concerns.js";

const STEP_LABELS = ["Counselor", "Date", "Time", "Session mode", "Review", "Submit"];

/** Guided counselor-first booking flow. The existing appointment mutation remains authoritative. */
export default function BookingModal({ open, onClose, state, rescheduleId = null,
  selfCounselorId = null, selfCounselorName = "" }) {
  const [step, setStep] = useState(1);
  const [selectedCounselorId, setSelectedCounselorId] = useState(null);
  const [selectedDate, setSelectedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [slotCandidates, setSlotCandidates] = useState([]);
  const [selectedSlotId, setSelectedSlotId] = useState(null);
  const [slotSelectionInitialized, setSlotSelectionInitialized] = useState(false);
  const [slotDetails, setSlotDetails] = useState(null);
  const [mode, setMode] = useState("ONLINE");
  const [concernCategories, setConcernCategories] = useState([]);
  const [concernDetails, setConcernDetails] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const resetSelection = () => {
    setStep(1); setSelectedCounselorId(null); setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
    setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setDone(false);
    setConcernCategories([]); setConcernDetails("");
    state.setCounselorUserId?.("");
  };
  useEffect(() => { if (!open) resetSelection(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const onKey = event => { if (event.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  // A Counselor can only reschedule against their own availability, and the
  // Student counselor directory is intentionally empty for them. Start those
  // flows on the calendar step so the modal never dead-ends at step 1.
  useEffect(() => {
    if (!open || selfCounselorId == null) return;
    setSelectedCounselorId(selfCounselorId);
    setStep(current => (current < 2 ? 2 : current));
  }, [open, selfCounselorId]);
  useEffect(() => {
    if (!open || !selectedDate) return;
    if (state.date !== selectedDate) state.setDate(selectedDate);
    if (state.slotPage !== 1) state.setSlotPage(1);
  }, [open, selectedDate, state.date, state.slotPage, state.setDate, state.setSlotPage]);
  useEffect(() => {
    if (!open || !selectedDate || !pickedTime || state.loading) return;
    const startEpoch = new Date(`${selectedDate}T${pickedTime}:00+08:00`).getTime();
    const matches = state.slots.items.filter(slot =>
      slot.status === "AVAILABLE"
      && slot.counselor_user_id === selectedCounselorId
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
      if (selfCounselorId != null) return;
      state.setCounselorUserId?.(""); setSelectedCounselorId(null); state.setDate("");
      setSelectedDate(null); setPickedTime(null); setSlotCandidates([]);
      setSelectedSlotId(null); setSlotSelectionInitialized(false); setSlotDetails(null); setMode("ONLINE"); setStep(1);
    }
  };
  const submit = async event => {
    event.preventDefault();
    const hasCustom = concernCategories.includes(CUSTOM_CONCERN.value);
    if (!slotDetails || submitting
      || (!rescheduleId && (!concernCategories.length || (hasCustom && !concernDetails.trim())))
      || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location)) return;
    setStep(6); setSubmitting(true);
    const path = rescheduleId ? `/appointments/${rescheduleId}/reschedule` : "/appointments";
    const payload = { availability_slot_id: slotDetails.slot_id, appointment_mode: mode };
    if (!rescheduleId) {
      payload.concern_categories = concernCategories;
      payload.concern_details = concernDetails.trim() || null;
    }
    const ok = await state.mutate(path,
      payload, "POST",
      rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review.");
    setSubmitting(false);
    if (ok) setDone(true);
    else setStep(5);
  };
  if (!open) return null;

  const stepTotal = STEP_LABELS.length;
  const progressPercent = Math.round((step / stepTotal) * 100);
  const subtitle = done ? "Request submitted" : `Step ${step} of ${stepTotal}: ${STEP_LABELS[step - 1]}`;
  const hasCustomConcern = concernCategories.includes(CUSTOM_CONCERN.value);
  const allStandardConcernsSelected = STANDARD_CONCERNS.every(option => concernCategories.includes(option.value));
  const confirmDisabled = submitting || state.busy || !slotDetails
    || (!rescheduleId && (!concernCategories.length || (hasCustomConcern && !concernDetails.trim())))
    || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location);
  const today = manilaToday();
  const availableModes = slotDetails?.delivery_mode === "BOTH" ? ["ONLINE", "FACE_TO_FACE"]
    : slotDetails ? [slotDetails.delivery_mode] : [];
  const existingAppointment = rescheduleId == null ? null
    : state.appointments.items.find(item => item.appointment_id === rescheduleId);
  const canContinueFromTime = Boolean(slotDetails && (rescheduleId
    || (concernCategories.length && (!hasCustomConcern || concernDetails.trim()))));

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
              <p className="booking-hint">Counselor: {state.bookingCounselors.find(item => item.counselor_user_id === selectedCounselorId)?.counselor_name ?? selfCounselorName}</p>
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
              {slotDetails && (rescheduleId
                ? <ConcernSummary categories={existingAppointment?.concern_categories} details={existingAppointment?.concern_details} className="mt-5 rounded-lg bg-emerald-50 p-3" />
                : <fieldset className="mt-5 rounded-lg border border-slate-200 p-3" aria-describedby="booking-concern-help">
                  <legend className="px-1 text-sm font-semibold text-slate-800">What would you like support with?</legend>
                  <p id="booking-concern-help" className="mb-3 text-xs text-slate-500">Select one or more. Your first selection is the priority topic and is shared only with you and your assigned Counselor.</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {STANDARD_CONCERNS.map(option => <label key={option.value} className="flex items-center gap-2 text-sm text-slate-700">
                      <input type="checkbox" checked={concernCategories.includes(option.value)}
                        onChange={() => setConcernCategories(current => toggleConcernCategory(current, option.value))} />
                      {option.label}
                    </label>)}
                    <label className="flex items-center gap-2 text-sm text-slate-700">
                      <input type="checkbox" checked={allStandardConcernsSelected}
                        onChange={() => setConcernCategories(current => toggleConcernCategory(current, ALL_CONCERNS_VALUE))} />
                      All of the above
                    </label>
                    <label className="flex items-center gap-2 text-sm text-slate-700">
                      <input type="checkbox" checked={hasCustomConcern}
                        onChange={() => setConcernCategories(current => toggleConcernCategory(current, CUSTOM_CONCERN.value))} />
                      {CUSTOM_CONCERN.label}
                    </label>
                  </div>
                  {concernCategories.length > 0 && <p role="status" className="mt-3 text-xs text-emerald-800">
                    Priority: {concernCategories[0].toLowerCase().replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase())}
                    {concernCategories.length > 1 ? ` · ${concernCategories.length - 1} additional topic${concernCategories.length === 2 ? "" : "s"}` : ""}
                  </p>}
                  {concernCategories.length > 0 && <label className="booking-field mt-3" htmlFor="booking-concern-details">
                    More details {hasCustomConcern ? "(required with Custom)" : "(optional)"}
                    <textarea id="booking-concern-details" className="booking-select" rows={3} maxLength={500}
                      required={hasCustomConcern} value={concernDetails} onChange={event => setConcernDetails(event.target.value)} />
                    <span className="text-xs text-slate-500">{concernDetails.length}/500 characters</span>
                  </label>}
                </fieldset>)}
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
              {step === 5 && (rescheduleId
                ? <ConcernSummary categories={existingAppointment?.concern_categories} details={existingAppointment?.concern_details} className="mt-4 rounded-lg bg-emerald-50 p-3" />
                : <ConcernSummary categories={concernCategories} details={concernDetails} className="mt-4 rounded-lg bg-emerald-50 p-3" />)}
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
            {step > 1 && step < 6 && !(step === 2 && selfCounselorId != null)
              && <button type="button" className="booking-btn-text" disabled={submitting || state.busy} onClick={back}>‹ Back</button>}
            <button type="button" className="booking-btn-text" onClick={onClose}>Cancel</button>
          </div>
          {step === 3 && <button type="button" className={`${buttonClass} booking-btn-primary`} disabled={!canContinueFromTime || state.loading}
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
