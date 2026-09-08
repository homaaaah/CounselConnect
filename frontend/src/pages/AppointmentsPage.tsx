import { useState } from "react";
import type { SessionUser } from "../features/auth";
import { useAppointments, formatSchedule, manilaInputToUTC, type Appointment, type Slot } from "../features/appointments";

const inputClass = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";
const buttonClass = "rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50";
const secondaryClass = "rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50";
const modeLabel = (mode: string) => mode === "ONLINE" ? "Online" : mode === "BOTH" ? "Online or face-to-face" : "Face-to-face";
type Controller = ReturnType<typeof useAppointments>;

function Pagination({ page, total, onChange, disabled }: { page: number; total: number; onChange: (p: number) => void; disabled: boolean }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function AvailabilityForm({ state }: { state: Controller }) {
  const [campusId, setCampusId] = useState("");
  const [location, setLocation] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [duration, setDuration] = useState("");
  const [mode, setMode] = useState("ONLINE");
  const [validation, setValidation] = useState("");
  const campus = state.campuses.find(c => c.campus_id === Number(campusId));
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <h2 className="text-lg font-semibold">Set availability</h2>
    <p className="mt-1 text-sm text-slate-500">Enter your schedule in Philippine time. Students request a slot for your review.</p>
    <label className="mt-4 block text-sm">Campus
      <select className={inputClass} value={campusId} disabled={state.busy} onChange={e => { setCampusId(e.target.value); setLocation(""); }}>
        <option value="">Select campus</option>
        {state.campuses.map(c => <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>)}
      </select>
    </label>
    {campus && <form className="mt-4 rounded-lg bg-slate-50 p-4" onSubmit={async e => {
      e.preventDefault();
      if (await state.mutate("/campuses/" + campusId + "/guidance-office-location", { guidance_office_location: location.trim() }, "PATCH", "Guidance Office location saved.")) setLocation("");
    }}>
      <p className="text-sm">Current Guidance Office: {campus.guidance_office_location || "Not configured"}</p>
      <label className="mt-2 block text-sm">New Guidance Office location
        <input className={inputClass} required maxLength={255} value={location} onChange={e => setLocation(e.target.value)} />
      </label>
      <button className={secondaryClass + " mt-2"} disabled={state.busy || !location.trim()}>Save location</button>
    </form>}
    <form className="mt-4 space-y-4" onSubmit={async e => {
      e.preventDefault(); setValidation("");
      if (!campusId) { setValidation("Select a campus."); return; }
      const startsAt = manilaInputToUTC(start), endsAt = manilaInputToUTC(end);
      const minutes = (new Date(endsAt).getTime() - new Date(startsAt).getTime()) / 60000;
      if (minutes <= 0 || minutes % Number(duration) || minutes / Number(duration) > 200) {
        setValidation("Choose a range containing 1 to 200 whole slots of the selected duration."); return;
      }
      await state.mutate("/availability-slots", { campus_id: Number(campusId), delivery_mode: mode,
        starts_at: startsAt, ends_at: endsAt, slot_duration_minutes: Number(duration) }, "POST", "Availability slots created.");
    }}>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm">Starts (Philippine time)<input className={inputClass} type="datetime-local" required value={start} onChange={e => setStart(e.target.value)} /></label>
        <label className="text-sm">Ends (Philippine time)<input className={inputClass} type="datetime-local" required value={end} onChange={e => setEnd(e.target.value)} /></label>
        <label className="text-sm">Slot duration (minutes)<input className={inputClass} type="number" min="1" step="1" required value={duration} onChange={e => setDuration(e.target.value)} /></label>
        <label className="text-sm">Supported mode<select className={inputClass} value={mode} onChange={e => setMode(e.target.value)}>
          <option value="ONLINE">Online</option><option value="FACE_TO_FACE">Face-to-face</option><option value="BOTH">Both</option>
        </select></label>
      </div>
      {mode !== "ONLINE" && !campus?.guidance_office_location && <p className="text-sm text-amber-700">Save a Guidance Office location before offering face-to-face sessions.</p>}
      {validation && <p role="alert" className="text-sm text-red-700">{validation}</p>}
      <button className={buttonClass} disabled={state.busy || !campusId || (mode !== "ONLINE" && !campus?.guidance_office_location)}>Create slots</button>
    </form>
  </section>;
}

function SlotCard({ slot, state, canBook, rescheduleId, onBooked }: {
  slot: Slot; state: Controller; canBook: boolean; rescheduleId: number | null; onBooked: () => void;
}) {
  const [mode, setMode] = useState(slot.delivery_mode === "FACE_TO_FACE" ? "FACE_TO_FACE" : "ONLINE");
  return <li className="rounded-lg border border-slate-200 p-4">
    <h3 className="font-medium">{formatSchedule(slot.starts_at)}</h3>
    <p className="text-sm text-slate-600">Until {formatSchedule(slot.ends_at)}</p>
    <p className="mt-2 text-sm">{slot.campus_name} · {slot.counselor_name}</p>
    <p className="text-sm text-slate-600">{modeLabel(slot.delivery_mode)} · {slot.status === "AVAILABLE" ? "Available" : "Reserved"}</p>
    {slot.delivery_mode !== "FACE_TO_FACE" && <p className="mt-1 text-sm text-slate-600">Online sessions cannot be joined in the app yet.</p>}
    {slot.delivery_mode !== "ONLINE" && <p className="mt-1 text-sm text-slate-600">Guidance Office: {slot.guidance_office_location || "Not configured"}</p>}
    {canBook && slot.status === "AVAILABLE" && <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={async e => {
      e.preventDefault();
      const path = rescheduleId ? "/appointments/" + rescheduleId + "/reschedule" : "/appointments";
      if (await state.mutate(path, { availability_slot_id: slot.slot_id, appointment_mode: mode }, "POST",
        rescheduleId ? "Rescheduled. Awaiting counselor review." : "Request submitted. Awaiting counselor review.")) onBooked();
    }}>
      <label className="text-sm">Appointment mode<select className={inputClass} value={mode} onChange={e => setMode(e.target.value)}>
        {slot.delivery_mode !== "FACE_TO_FACE" && <option value="ONLINE">Online</option>}
        {slot.delivery_mode !== "ONLINE" && <option value="FACE_TO_FACE">Face-to-face</option>}
      </select></label>
      <button className={buttonClass} disabled={state.busy || state.loading || (mode === "FACE_TO_FACE" && !slot.guidance_office_location)}>
        {rescheduleId ? "Choose replacement" : "Request appointment"}
      </button>
    </form>}
  </li>;
}

function AppointmentCard({ appointment: a, state, counselor, onReschedule }: {
  appointment: Appointment; state: Controller; counselor: boolean; onReschedule: (id: number) => void;
}) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const action = (name: string, body?: unknown) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
  const active = a.status === "PENDING" || a.status === "CONFIRMED";
  const started = new Date(a.starts_at).getTime() <= Date.now();
  return <li className="rounded-lg border border-slate-200 p-5">
    <div className="flex flex-wrap justify-between gap-2">
      <h3 className="font-semibold">{formatSchedule(a.starts_at)}</h3>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{a.status.replaceAll("_", " ")}</span>
    </div>
    <p className="text-sm text-slate-500">Until {formatSchedule(a.ends_at)} · {a.campus_name}</p>
    <p className="mt-3 text-sm">{counselor ? "Student: " + a.student_name : "Counselor: " + a.counselor_name}</p>
    <p className="text-sm">{modeLabel(a.appointment_mode)}</p>
    {a.meeting_location && <p className="mt-1 text-sm">Guidance Office: {a.meeting_location}</p>}
    {a.rejection_note && <p className="mt-2 text-sm text-slate-600">Counselor note: {a.rejection_note}</p>}
    {a.status === "PENDING" && <p className="mt-2 text-sm text-amber-700">Awaiting counselor review.</p>}
    {a.status === "CONFIRMED" && a.appointment_mode === "ONLINE" && <p className="mt-2 text-sm text-slate-600">Online appointment confirmed. In-app Live Chat is not available yet.</p>}
    <div className="mt-4 flex flex-wrap gap-2">
      {counselor && a.status === "PENDING" && <>
        <button className={buttonClass} disabled={state.busy || started} onClick={() => void action("confirm")}>Confirm</button>
        <button className={secondaryClass} disabled={state.busy} onClick={() => setRejecting(!rejecting)}>Reject</button>
      </>}
      {active && <button className={secondaryClass} disabled={state.busy} onClick={() => setCancelling(!cancelling)}>Cancel appointment</button>}
      {a.status === "CONFIRMED" && a.conversation_id === null && <button className={secondaryClass} disabled={state.busy} onClick={() => onReschedule(a.appointment_id)}>Reschedule</button>}
      {counselor && a.status === "CONFIRMED" && <>
        <button className={buttonClass} disabled={state.busy || !started} onClick={() => void action("complete")}>Mark completed</button>
        <button className={secondaryClass} disabled={state.busy || !started} onClick={() => void action("no-show")}>Mark no-show</button>
      </>}
    </div>
    {cancelling && active && <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm">
      <p>Cancel this appointment and release the slot?</p>
      <button className={secondaryClass + " mt-2"} disabled={state.busy} onClick={async () => { if (await action("cancel")) setCancelling(false); }}>Confirm cancellation</button>
    </div>}
    {rejecting && a.status === "PENDING" && <form className="mt-3" onSubmit={async e => {
      e.preventDefault(); if (await action("reject", { rejection_note: note.trim() || null })) setRejecting(false);
    }}>
      <label className="text-sm">Reason (optional)<textarea className={inputClass} maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></label>
      <button className={secondaryClass} disabled={state.busy}>Reject request</button>
    </form>}
  </li>;
}

export default function AppointmentsPage({ user }: { user: SessionUser }) {
  const state = useAppointments();
  const counselor = user.role_code === "COUNSELOR";
  const [rescheduleId, setRescheduleId] = useState<number | null>(null);
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-5xl space-y-6">
      <header><h1 className="text-2xl font-bold">{counselor ? "Manage appointments" : "My appointments"}</h1>
        <p className="mt-1 text-sm text-slate-500">All dates and times are shown in Philippine time (Asia/Manila).</p>
        <button className={secondaryClass + " mt-3"} disabled={state.busy || state.loading} onClick={() => void state.refresh()}>Refresh appointments</button>
      </header>
      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving…</p>}
      {counselor && <AvailabilityForm state={state} />}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">{rescheduleId ? "Choose a replacement slot" : counselor ? "Your availability" : "Find an available slot"}</h2>
        {rescheduleId && <div className="mt-2 text-sm"><p>Your current appointment stays reserved until a replacement is accepted. The new request needs counselor review.</p>
          <button className={secondaryClass + " mt-2"} onClick={() => setRescheduleId(null)}>Stop rescheduling</button></div>}
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Campus<select className={inputClass} disabled={state.busy} value={state.campusId} onChange={e => { state.setCampusId(e.target.value); state.setSlotPage(1); }}>
            <option value="">All campuses</option>{state.campuses.map(c => <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>)}
          </select></label>
          <label className="text-sm">Date<input className={inputClass} disabled={state.busy} type="date" value={state.date} onChange={e => { state.setDate(e.target.value); state.setSlotPage(1); }} /></label>
          <label className="text-sm">Mode<select className={inputClass} disabled={state.busy} value={state.mode} onChange={e => { state.setMode(e.target.value); state.setSlotPage(1); }}>
            <option value="">All modes</option><option value="ONLINE">Online</option><option value="FACE_TO_FACE">Face-to-face</option>
          </select></label>
        </div>
        {state.loading ? <p role="status" className="mt-4">Loading appointments…</p> : <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {state.slots.items.map(slot => <SlotCard key={slot.slot_id + ":" + slot.delivery_mode} slot={slot} state={state} canBook={!counselor || rescheduleId !== null} rescheduleId={rescheduleId} onBooked={() => setRescheduleId(null)} />)}
        </ul>}
        {!state.loading && !state.error && state.slots.items.length === 0 && <p className="mt-4 text-sm text-slate-500">No slots match these filters.</p>}
        <Pagination page={state.slotPage} total={state.slots.total} onChange={state.setSlotPage} disabled={state.busy || state.loading} />
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4"><h2 className="text-lg font-semibold">{counselor ? "Requests and outcomes" : "Your requests and history"}</h2>
          <label className="text-sm">Status<select className={inputClass} disabled={state.busy} value={state.status} onChange={e => { state.setStatus(e.target.value); state.setAppointmentPage(1); }}>
            <option value="">All statuses</option>{["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED", "REJECTED", "NO_SHOW"].map(s => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}
          </select></label></div>
        {!state.loading && <ul className="mt-4 space-y-4">{state.appointments.items.map(a => <AppointmentCard key={a.appointment_id} appointment={a} state={state} counselor={counselor} onReschedule={setRescheduleId} />)}</ul>}
        {!state.loading && !state.error && state.appointments.items.length === 0 && <p className="mt-4 text-sm text-slate-500">No appointments yet.</p>}
        <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.loading} />
      </section>
    </div>
  </main>;
}
