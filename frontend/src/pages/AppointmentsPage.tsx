import { useState } from "react";
import type { SessionUser } from "../features/auth";
import { useAppointments, formatSchedule, manilaInputToUTC, type Appointment, type Slot } from "../features/appointments";

const inputClass = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";
const buttonClass = "rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50";
const secondaryClass = "rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50";
const modeLabel = (mode: string) => mode === "ONLINE" ? "Online" : mode === "BOTH" ? "Online or face-to-face" : "Face-to-face";
const dayLabel = (day: number) => ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day];
const timeLabel = (value: string) => value.slice(0, 5);
type Controller = ReturnType<typeof useAppointments>;

function Pagination({ page, total, onChange, disabled }: { page: number; total: number; onChange: (p: number) => void; disabled: boolean }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function CalendarView({ state, counselor }: { state: Controller; counselor: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const days = Array.isArray(state.calendar?.days) ? state.calendar.days : [];
  const selectedDay = days.find(day => day.calendar_date === selected);
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{counselor ? "Counselor calendar" : "Available appointments"}</h2>
        <p className="mt-1 text-sm text-slate-500">{state.calendar?.business_hours || "Monday-Friday, 8:00 AM-4:00 PM"} · Philippine time</p></div>
      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">Live dates</span>
    </div>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {days.map(day => <button key={day.calendar_date} type="button" disabled={day.is_blocked || !day.is_weekday}
        onClick={() => setSelected(day.calendar_date)} className={`rounded-lg border p-3 text-left ${selected === day.calendar_date ? "border-emerald-600 ring-2 ring-emerald-100" : "border-slate-200"} ${day.is_blocked ? "bg-red-50 text-red-700" : day.is_weekday ? "bg-white hover:border-emerald-400" : "bg-slate-50 text-slate-400"}`}>
        <p className="font-medium">{new Date(day.calendar_date + "T00:00:00").toLocaleDateString("en-PH", { weekday: "short", month: "short", day: "numeric" })}</p>
        <p className="mt-1 text-xs">{day.is_blocked ? "Unavailable" : !day.is_weekday ? "Weekend" : `${day.available_times.length} times available`}</p>
      </button>)}
    </div>
    {selectedDay && !selectedDay.is_blocked && <div className="mt-5 rounded-lg bg-slate-50 p-4"><p className="text-sm font-medium">Times for {selectedDay.calendar_date}</p>
      <div className="mt-3 flex flex-wrap gap-2">{selectedDay.available_times.map(time => <button key={time} type="button" className={secondaryClass} onClick={() => { state.setDate(selectedDay.calendar_date); }}>{time}</button>)}</div>
      <p className="mt-3 text-xs text-slate-500">Select a time to filter the appointment list below.</p>
    </div>}
    {counselor && <BlockDateForm state={state} />}
  </section>;
}

function BlockDateForm({ state }: { state: Controller }) {
  const [date, setDate] = useState(""); const [reason, setReason] = useState("");
  return <form className="mt-5 border-t border-slate-200 pt-5" onSubmit={async event => { event.preventDefault(); if (await state.mutate("/calendar/blocks", { blocked_date: date, reason: reason.trim() || null }, "POST", "Date blocked. Students can no longer request it.")) { setDate(""); setReason(""); } }}>
    <h3 className="font-medium">Block an unavailable date</h3><p className="mt-1 text-sm text-slate-500">Default face-to-face hours are Monday-Friday, 8:00 AM-4:00 PM.</p>
    <div className="mt-3 flex flex-wrap items-end gap-3"><label className="text-sm">Date<input className={inputClass} type="date" required min={new Date().toISOString().slice(0, 10)} value={date} onChange={e => setDate(e.target.value)} /></label><label className="text-sm">Reason (optional)<input className={inputClass} maxLength={255} value={reason} onChange={e => setReason(e.target.value)} /></label><button className={buttonClass} disabled={state.busy}>Block date</button></div>
  </form>;
}

function WeeklyScheduleSection({ state }: { state: Controller }) {
  const [campusId, setCampusId] = useState("");
  const [day, setDay] = useState("1");
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("10:00");
  const [duration, setDuration] = useState("30");
  const [mode, setMode] = useState("ONLINE");
  const minutes = (value: string) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
  const wholeSlots = (Number(end.slice(0, 2)) * 60 + Number(end.slice(3, 5)) - minutes(start)) % Number(duration) === 0;
  const campus = state.campuses.find(c => String(c.campus_id) === campusId);
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <h2 className="text-lg font-semibold">Recurring weekly schedule</h2>
    <p className="mt-1 text-sm text-slate-500">Repeats every week until you disable it. Existing appointments are not changed. Philippine local times.</p>
    <form className="mt-4 grid gap-3 sm:grid-cols-3" onSubmit={async event => {
      event.preventDefault();
      if (await state.mutate("/weekly-schedules", {
        campus_id: Number(campusId), day_of_week: Number(day), start_time: start + ":00", end_time: end + ":00",
        slot_duration_minutes: Number(duration), delivery_mode: mode,
      }, "POST", "Weekly schedule saved.")) { setDay("1"); setStart("08:00"); setEnd("10:00"); setDuration("30"); setMode("ONLINE"); }
    }}>
      <label className="text-sm">Campus<select className={inputClass} required disabled={state.busy} value={campusId} onChange={e => setCampusId(e.target.value)}>
        <option value="">Select a campus</option>{state.campuses.map(c => <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>)}
      </select></label>
      <label className="text-sm">Day<select className={inputClass} required disabled={state.busy} value={day} onChange={e => setDay(e.target.value)}>
        {[1, 2, 3, 4, 5, 6, 7].map(d => <option key={d} value={d}>{dayLabel(d)}</option>)}
      </select></label>
      <label className="text-sm">Mode<select className={inputClass} required disabled={state.busy} value={mode} onChange={e => setMode(e.target.value)}>
        <option value="ONLINE">Online only</option><option value="FACE_TO_FACE">Face-to-face only</option><option value="BOTH">Both</option>
      </select></label>
      <label className="text-sm">Start time<input className={inputClass} type="time" required step={60} disabled={state.busy} value={start} onChange={e => setStart(e.target.value)} /></label>
      <label className="text-sm">End time<input className={inputClass} type="time" required step={60} disabled={state.busy} value={end} onChange={e => setEnd(e.target.value)} /></label>
      <label className="text-sm">Slot minutes<select className={inputClass} required disabled={state.busy} value={duration} onChange={e => setDuration(e.target.value)}>
        {[15, 20, 30, 45, 60, 90, 120, 240].map(m => <option key={m} value={m}>{m}</option>)}
      </select></label>
      <div className="sm:col-span-3">
        {mode !== "ONLINE" && campus && !campus.guidance_office_location && <p role="alert" className="text-sm text-amber-700">This campus has no Guidance Office location. Face-to-face availability needs one first.</p>}
        {!wholeSlots && <p role="alert" className="text-sm text-amber-700">The time range must contain whole {duration}-minute slots.</p>}
        <button className={buttonClass + " mt-3"} disabled={state.busy || !campusId || !wholeSlots}>Save weekly schedule</button>
      </div>
    </form>
    {state.weeklySchedules.length > 0 && <ul className="mt-5 space-y-2">
      {state.weeklySchedules.map(s => <li key={s.weekly_schedule_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
        <span>{dayLabel(s.day_of_week)} · {timeLabel(s.start_time)}–{timeLabel(s.end_time)} · {s.slot_duration_minutes}-minute slots · {modeLabel(s.delivery_mode)} · {state.campuses.find(c => c.campus_id === s.campus_id)?.campus_name || "Campus " + s.campus_id}</span>
        {s.is_active
          ? <button className={secondaryClass} disabled={state.busy} onClick={() => void state.mutate("/weekly-schedules/" + s.weekly_schedule_id, undefined, "DELETE", "Weekly schedule disabled.")}>Disable</button>
          : <span className="text-slate-400">Disabled</span>}
      </li>)}
    </ul>}
  </section>;
}

function AvailabilityBlocksSection({ state }: { state: Controller }) {
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [reason, setReason] = useState("");
  const [blocking, setBlocking] = useState(false);
  const now = new Date();
  const minLocal = new Date(now.getTime() + 60 * 60 * 1000).toISOString().slice(0, 16);
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <h2 className="text-lg font-semibold">Temporary unavailable time</h2>
    <p className="mt-1 text-sm text-slate-500">Blocks hide future slots without changing your weekly schedule. A block cannot overlap a pending or confirmed appointment.</p>
    {blocking
      ? <form className="mt-4" onSubmit={async event => {
        event.preventDefault();
        if (await state.mutate("/availability-blocks", {
          starts_at: manilaInputToUTC(rangeStart), ends_at: manilaInputToUTC(rangeEnd),
          is_all_day: false, reason: reason.trim() || null,
        }, "POST", "Unavailable time saved.")) { setBlocking(false); setRangeStart(""); setRangeEnd(""); setReason(""); }
      }}>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">Starts<input className={inputClass} type="datetime-local" required min={minLocal} disabled={state.busy} value={rangeStart} onChange={e => setRangeStart(e.target.value)} /></label>
          <label className="text-sm">Ends<input className={inputClass} type="datetime-local" required disabled={state.busy} value={rangeEnd} onChange={e => setRangeEnd(e.target.value)} /></label>
          <label className="text-sm">Reason (optional)<input className={inputClass} maxLength={255} disabled={state.busy} value={reason} onChange={e => setReason(e.target.value)} /></label>
        </div>
        {rangeStart && rangeEnd && new Date(rangeEnd) <= new Date(rangeStart) && <p role="alert" className="mt-2 text-sm text-amber-700">The end must be after the start.</p>}
        <div className="mt-3 flex gap-2">
          <button className={buttonClass} disabled={state.busy || !rangeStart || !rangeEnd || new Date(rangeEnd) <= new Date(rangeStart)}>Save unavailable time</button>
          <button type="button" className={secondaryClass} disabled={state.busy} onClick={() => setBlocking(false)}>Cancel</button>
        </div>
      </form>
      : <button className={buttonClass + " mt-4"} disabled={state.busy} onClick={() => setBlocking(true)}>Block unavailable time</button>}
    {state.availabilityBlocks.length > 0 && <ul className="mt-5 space-y-2">
      {state.availabilityBlocks.map(b => <li key={b.availability_block_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
        <span>{formatSchedule(b.starts_at)} – {formatSchedule(b.ends_at)}{b.reason ? " · " + b.reason : ""}</span>
        <button className={secondaryClass} disabled={state.busy} onClick={() => void state.mutate("/availability-blocks/" + b.availability_block_id, undefined, "DELETE", "Unavailable time removed.")}>Remove</button>
      </li>)}
    </ul>}
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
  const state = useAppointments(user.role_code);
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
      <CalendarView state={state} counselor={counselor} />
      {counselor && <WeeklyScheduleSection state={state} />}
      {counselor && <AvailabilityBlocksSection state={state} />}
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
