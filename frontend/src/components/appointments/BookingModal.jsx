import { useEffect, useState } from "react";
import { formatSchedule } from "../../features/appointments";
import { buttonClass, secondaryClass, modeLabel } from "./ui.js";
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
 * keeps the calendar visible with the error below it.
 */
export default function BookingModal({ open, onClose, state, rescheduleId = null }) {
  const [selectedDate, setSelectedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [slotDetails, setSlotDetails] = useState(null);
  const [mode, setMode] = useState("ONLINE");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const resetSelection = () => {
    setSelectedDate(null); setPickedTime(null); setSlotDetails(null);
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

  // Match the picked time to a loaded slot once that date's slots arrive.
  useEffect(() => {
    if (!open || !selectedDate || !pickedTime || state.loading) return;
    const startEpoch = new Date(selectedDate + "T" + pickedTime + ":00+08:00").getTime();
    const match = state.slots.items.find(s => new Date(s.starts_at).getTime() === startEpoch) ?? null;
    setSlotDetails(match);
    if (match) setMode(match.delivery_mode === "FACE_TO_FACE" ? "FACE_TO_FACE" : "ONLINE");
  }, [open, selectedDate, pickedTime, state.loading, state.slots]);

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
    // On failure state.mutate surfaces state.error below the calendar; the
    // details form stays visible so the visitor can change time or retry
    // (the server rejects stale slots again with SLOT_UNAVAILABLE).
  };

  if (!open) return null;

  return <div className="modal-overlay" role="dialog" aria-modal="true"
    aria-label={rescheduleId ? "Reschedule appointment" : "Schedule an appointment"}
    onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
    <div className="modal-card booking-modal-card">
      <button type="button" className="modal-close" onClick={onClose} aria-label="Close dialog">
        <i className="fa-solid fa-xmark" aria-hidden="true"></i>
      </button>

      {done
        ? <>
            <h2 className="text-xl font-semibold">{rescheduleId ? "Reschedule requested" : "Appointment requested"}</h2>
            <p role="status" className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
              {rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review."}
            </p>
            <button type="button" className={buttonClass + " mt-4"} onClick={onClose}>Close</button>
          </>
        : <>
            <h2 className="text-xl font-semibold">{rescheduleId ? "Reschedule appointment" : "Schedule an appointment"}</h2>
            <p className="mt-1 text-sm text-slate-500">Click a date to see available times, then pick one to reveal campus and mode details. Philippine time.</p>

            {!state.calendar && state.loading
              ? <p role="status" className="mt-4">Loading calendar…</p>
              : <>
                  <div className="mt-4">
                    <CalendarGrid calendar={state.calendar}
                      onSelect={() => { setPickedTime(null); setSlotDetails(null); }}
                      onPickTime={(date, time) => { setSelectedDate(date); setPickedTime(time); }} />
                  </div>

                  {state.error && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{state.error}</p>}

                  {selectedDate && !pickedTime && <p className="mt-3 text-sm text-slate-500">Pick a time on your selected date to continue.</p>}
                  {pickedTime && state.loading && <p role="status" className="mt-3 text-sm text-slate-500">Loading slot details…</p>}

                  {pickedTime && !state.loading && !slotDetails &&
                    <p role="alert" className="mt-3 text-sm text-amber-700">That time is no longer available. Please pick another time.</p>}

                  {pickedTime && !state.loading && slotDetails && <form className="mt-5 rounded-lg bg-white p-4" onSubmit={submit}>
                    <p className="text-sm font-medium">Additional information</p>
                    <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                      <div><dt className="text-slate-500">Campus</dt><dd className="font-medium">{slotDetails.campus_name}</dd></div>
                      <div><dt className="text-slate-500">Time</dt><dd className="font-medium">{formatSchedule(slotDetails.starts_at)} – {formatSchedule(slotDetails.ends_at)}</dd></div>
                      <div><dt className="text-slate-500">Counselor</dt><dd className="font-medium">{slotDetails.counselor_name}</dd></div>
                      <div><dt className="text-slate-500">Mode</dt><dd className="font-medium">{modeLabel(slotDetails.delivery_mode)}</dd></div>
                      {slotDetails.guidance_office_location && <div className="sm:col-span-2"><dt className="text-slate-500">Guidance Office</dt><dd className="font-medium">{slotDetails.guidance_office_location}</dd></div>}
                    </dl>
                    <label className="mt-3 block text-sm">Appointment mode
                      <select className="mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm" value={mode} onChange={e => setMode(e.target.value)}>
                        {slotDetails.delivery_mode !== "FACE_TO_FACE" && <option value="ONLINE">Online</option>}
                        {slotDetails.delivery_mode !== "ONLINE" && <option value="FACE_TO_FACE">Face-to-face</option>}
                      </select>
                    </label>
                    {slotDetails.delivery_mode !== "ONLINE" && !slotDetails.guidance_office_location && (
                      <p role="alert" className="mt-2 text-sm text-amber-700">This campus has no Guidance Office location yet; face-to-face booking is unavailable for this slot.</p>
                    )}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button className={buttonClass} disabled={submitting || state.busy || (mode === "FACE_TO_FACE" && !slotDetails.guidance_office_location)}>
                        {rescheduleId ? "Confirm reschedule" : "Confirm booking"}
                      </button>
                      <button type="button" className={secondaryClass} disabled={submitting || state.busy} onClick={() => { setPickedTime(null); setSlotDetails(null); }}>Change time</button>
                    </div>
                  </form>}
                </>}
          </>}
    </div>
  </div>;
}
