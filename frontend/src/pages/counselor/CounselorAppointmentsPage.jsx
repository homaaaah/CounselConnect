import { useState } from "react";
import { useAppointments, formatSchedule, manilaInputToUTC, manilaLocalInput, manilaToday } from "../../features/appointments";
import { buttonClass, secondaryClass, inputClass, modeLabel, dayLabel, timeLabel } from "../../components/appointments/ui.js";
import CalendarGrid from "../../components/appointments/CalendarGrid.jsx";
import BookingModal from "../../components/appointments/BookingModal.jsx";

function Pagination({ page, total, onChange, disabled }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function AppointmentCard({ appointment: a, state, counselor, onReschedule }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const action = (name, body) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
  const active = a.status === "PENDING" || a.status === "CONFIRMED";
  const started = new Date(a.starts_at).getTime() <= Date.now();
  const canCancel = a.can_cancel ?? active;
  const canReschedule = a.can_reschedule ?? (a.status === "CONFIRMED" && a.conversation_id === null);
  const canChangeMode = a.can_change_mode ?? false;
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
    {a.status === "CONFIRMED" && a.appointment_mode === "ONLINE" && <p className="mt-2 text-sm text-slate-600">Online appointment confirmed. The session lobby opens 30 minutes before the scheduled start.</p>}
    <div className="mt-4 flex flex-wrap gap-2">
      {counselor && a.status === "PENDING" && <>
        <button className={buttonClass} disabled={state.busy || started} onClick={() => void action("confirm")}>Confirm</button>
        <button className={secondaryClass} disabled={state.busy} onClick={() => setRejecting(!rejecting)}>Reject</button>
      </>}
      {canCancel && <button className={secondaryClass} disabled={state.busy} onClick={() => setCancelling(!cancelling)}>Cancel appointment</button>}
      {canReschedule && <button className={secondaryClass} disabled={state.busy} onClick={() => onReschedule(a.appointment_id)}>Reschedule</button>}
      {canChangeMode && <button className={secondaryClass} disabled={state.busy} onClick={() => void action("change-mode", { appointment_mode: a.appointment_mode === "ONLINE" ? "FACE_TO_FACE" : "ONLINE" })}>Change to {a.appointment_mode === "ONLINE" ? "face-to-face" : "online"}</button>}
      {counselor && a.status === "CONFIRMED" && <>
        <button className={buttonClass} disabled={state.busy || !started} onClick={() => void action("complete")}>Mark completed</button>
        <button className={secondaryClass} disabled={state.busy || !started} onClick={() => void action("no-show")}>Mark no-show</button>
      </>}
    </div>
    {cancelling && canCancel && <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm">
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

function RecordsTabs({ state }) {
  const recordsTabs = [
    ["CONFIRMED", "Confirmed"],
    ["PENDING", "Pending"],
    ["COMPLETED", "Completed"],
    ["NO_SHOW", "No-show"],
    ["CANCELLED", "Cancelled"],
    ["REJECTED", "Rejected"],
  ];
  return <div role="tablist" aria-label="Filter records by status" className="flex flex-wrap gap-2">
    {recordsTabs.map(([status, label]) => <button key={status} type="button" role="tab" aria-selected={state.status === status}
      className={state.status === status
        ? "rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white"
        : "rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"}
      onClick={() => { state.setStatus(status); state.setAppointmentPage(1); }}>{label}</button>)}
  </div>;
}

function BlockDateForm({ state }) {
  const [date, setDate] = useState(""); const [reason, setReason] = useState("");
  return <form className="mt-5 border-t border-slate-200 pt-5" onSubmit={async event => { event.preventDefault(); if (await state.mutate("/calendar/blocks", { blocked_date: date, reason: reason.trim() || null }, "POST", "Date blocked. Students can no longer request it.")) { setDate(""); setReason(""); } }}>
    <h3 className="font-medium">Block a whole date</h3><p className="mt-1 text-sm text-slate-500">Default face-to-face hours are Monday-Friday, 8:00 AM-4:00 PM.</p>
    <div className="mt-3 flex flex-wrap items-end gap-3"><label className="text-sm">Date<input className={inputClass} type="date" required min={manilaToday()} value={date} onChange={e => setDate(e.target.value)} /></label><label className="text-sm">Reason (optional)<input className={inputClass} maxLength={255} value={reason} onChange={e => setReason(e.target.value)} /></label><button className={buttonClass} disabled={state.busy}>Block date</button></div>
  </form>;
}

function WeeklyScheduleEditor({ state }) {
  const [editingId, setEditingId] = useState(null);
  const [campusId, setCampusId] = useState("");
  const [day, setDay] = useState("1");
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("10:00");
  const [duration, setDuration] = useState("30");
  const [mode, setMode] = useState("ONLINE");
  const minutes = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
  const wholeSlots = (Number(end.slice(0, 2)) * 60 + Number(end.slice(3, 5)) - minutes(start)) % Number(duration) === 0;
  const campus = state.campuses.find(c => String(c.campus_id) === campusId);

  const startEdit = (s) => {
    setEditingId(s.weekly_schedule_id);
    setCampusId(String(s.campus_id));
    setDay(String(s.day_of_week));
    setStart(s.start_time.slice(0, 5));
    setEnd(s.end_time.slice(0, 5));
    setDuration(String(s.slot_duration_minutes));
    setMode(s.delivery_mode);
  };

  const submit = async (event, replacingId = null) => {
    event.preventDefault();
    const path = replacingId
      ? "/weekly-schedules/" + replacingId + "/replace"
      : "/weekly-schedules";
    const saved = await state.mutate(path, {
      campus_id: Number(campusId), day_of_week: Number(day), start_time: start + ":00", end_time: end + ":00",
      slot_duration_minutes: Number(duration), delivery_mode: mode,
    }, "POST", replacingId ? "Availability updated." : "Weekly schedule saved.");
    if (saved) { setEditingId(null); setCampusId(""); setDay("1"); setStart("08:00"); setEnd("10:00"); setDuration("30"); setMode("ONLINE"); }
  };

  const activeSchedules = Array.isArray(state.weeklySchedules) ? state.weeklySchedules : (state.weeklySchedules?.items ?? []);
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <h2 className="text-lg font-semibold">Your weekly availability</h2>
    <p className="mt-1 text-sm text-slate-500">Edit the days, times, and campus you are available. Existing appointments are not changed. Philippine local times.</p>

    <form className="mt-4 grid gap-3 sm:grid-cols-3" onSubmit={(e) => submit(e, editingId)}>
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
      <label className="text-sm">End time<input className={inputClass} type="time" required disabled={state.busy} value={end} onChange={e => setEnd(e.target.value)} /></label>
      <label className="text-sm">Slot minutes<select className={inputClass} required disabled={state.busy} value={duration} onChange={e => setDuration(e.target.value)}>
        {[15, 20, 30, 45, 60, 90, 120, 240].map(m => <option key={m} value={m}>{m}</option>)}
      </select></label>
      <div className="sm:col-span-3">
        {mode !== "ONLINE" && campus && !campus.guidance_office_location && <p role="alert" className="text-sm text-amber-700">This campus has no Guidance Office location. Face-to-face availability needs one first.</p>}
        {!wholeSlots && <p role="alert" className="text-sm text-amber-700">The time range must contain whole {duration}-minute slots.</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <button className={buttonClass} disabled={state.busy || !campusId || !wholeSlots}>
            {editingId ? "Save changes" : "Add availability"}
          </button>
          {editingId && <button type="button" className={secondaryClass} disabled={state.busy} onClick={() => { setEditingId(null); setCampusId(""); setDay("1"); setStart("08:00"); setEnd("10:00"); setDuration("30"); setMode("ONLINE"); }}>Cancel edit</button>}
        </div>
      </div>
    </form>

    {activeSchedules.length === 0
      ? <p className="mt-5 rounded-lg bg-slate-50 p-4 text-sm text-slate-500">No weekly availability yet. Add your available campus, days, and times above — students will see open slots immediately.</p>
      : <ul className="mt-5 space-y-2" data-testid="weekly-availability-list">
        {activeSchedules.map(s => {
          const editing = editingId === s.weekly_schedule_id;
          return <li key={s.weekly_schedule_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
            <span>
              <span className="font-medium">{state.campuses.find(c => c.campus_id === s.campus_id)?.campus_name || "Campus " + s.campus_id}</span>
              {" · "}{dayLabel(s.day_of_week)}
              {" · "}{timeLabel(s.start_time)}–{timeLabel(s.end_time)}
              {" · "}{s.slot_duration_minutes}-minute slots
              {" · "}{modeLabel(s.delivery_mode)}
              {!s.is_active && " · disabled"}
            </span>
            <span className="flex gap-2">
              {s.is_active && !editing && <button className={secondaryClass} disabled={state.busy} onClick={() => startEdit(s)}>Edit</button>}
              {s.is_active && <button className={secondaryClass} disabled={state.busy} onClick={() => void state.mutate("/weekly-schedules/" + s.weekly_schedule_id, undefined, "DELETE", "Weekly schedule disabled.")}>Disable</button>}
            </span>
          </li>;
        })}
      </ul>}
  </section>;
}

function AvailabilityBlocksSection({ state }) {
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");
  const [reason, setReason] = useState("");
  const [blocking, setBlocking] = useState(false);
  const minLocal = manilaLocalInput(new Date(Date.now() + 60 * 60 * 1000));
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
    {state.availabilityBlocksError && <div role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
      <p>{state.availabilityBlocksError}</p>
      <button type="button" className={secondaryClass + " mt-2"} disabled={state.busy || state.availabilityBlocksLoading} onClick={() => void state.refresh()}>Retry unavailable times</button>
    </div>}
    {state.availabilityBlocksLoading && state.availabilityBlocks.length === 0 && <p role="status" className="mt-4 text-sm text-slate-500">Loading unavailable times…</p>}
    {!state.availabilityBlocksLoading && !state.availabilityBlocksError && state.availabilityBlocks.length === 0 && <p className="mt-4 text-sm text-slate-500">No temporary unavailable times.</p>}
    {Array.isArray(state.availabilityBlocks) && state.availabilityBlocks.length > 0 && <ul className="mt-5 space-y-2">
      {state.availabilityBlocks.map(b => <li key={b.availability_block_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
        <span>{formatSchedule(b.starts_at)} – {formatSchedule(b.ends_at)}{b.reason ? " · " + b.reason : ""}</span>
        <button className={secondaryClass} disabled={state.busy} onClick={() => void state.mutate("/availability-blocks/" + b.availability_block_id, undefined, "DELETE", "Unavailable time removed.")}>Remove</button>
      </li>)}
    </ul>}
  </section>;
}

export default function CounselorAppointmentsPage({ user }) {
  const state = useAppointments(user.role_code, "CONFIRMED");
  const [rescheduleId, setRescheduleId] = useState(null);
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Student appointments</h1>
        <p className="mt-1 text-sm text-slate-500">Review requests and manage your availability. Philippine time (Asia/Manila).</p>
        <button className={secondaryClass + " mt-3"} disabled={state.busy || state.loading} onClick={() => void state.refresh()}>Refresh records</button>
      </header>
      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving…</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-lg font-semibold">Student records</h2>
          <RecordsTabs state={state} />
        </div>
        {state.recordsError && <p role="alert" className="mt-4 text-sm text-red-700">{state.recordsError}</p>}
        {!state.recordsLoading && <ul className="mt-4 space-y-4">{state.appointments.items.map(a =>
          <AppointmentCard key={a.appointment_id} appointment={a} state={state} counselor={true} onReschedule={setRescheduleId} />)}</ul>}
        {!state.recordsLoading && !state.recordsError && state.appointments.items.length === 0 &&
          <p className="mt-4 text-sm text-slate-500">No {state.status ? state.status.replaceAll("_", " ").toLowerCase() : ""} student appointments yet.</p>}
        <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.recordsLoading} />
      </section>

      <BookingModal open={rescheduleId !== null} onClose={() => setRescheduleId(null)} state={state} rescheduleId={rescheduleId} />

      <WeeklyScheduleEditor state={state} />

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold">Your availability calendar</h2>
        <p className="mt-1 text-sm text-slate-500">Live dates · click a date to reveal its remaining times. The student side sees the same open dates.</p>
        <div className="mt-4"><CalendarGrid calendar={state.calendar} /></div>
        <BlockDateForm state={state} />
      </section>

      <AvailabilityBlocksSection state={state} />
    </div>
  </main>;
}
