import { useEffect, useState } from "react";
import { useAppointments, formatSchedule, manilaInputToUTC, manilaLocalInput, manilaToday, slotIsPast } from "../features/appointments";

const inputClass = "mt-1 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm";
const buttonClass = "rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50";
const secondaryClass = "rounded-md border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50";
const modeLabel = (mode) => mode === "ONLINE" ? "Online" : mode === "BOTH" ? "Online or face-to-face" : "Face-to-face";
const dayLabel = (day) => ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day];
const timeLabel = (value) => value.slice(0, 5);

function Pagination({ page, total, onChange, disabled }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function CalendarView({ state, counselor }) {
  const [selected, setSelected] = useState(null);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = setInterval(update, 1000);
    window.addEventListener("focus", update);
    return () => { clearInterval(timer); window.removeEventListener("focus", update); };
  }, []);
  const currentTime = Math.max(now, Date.now());
  const days = (Array.isArray(state.calendar?.days) ? state.calendar.days : []).map(day => ({
    ...day,
    is_past: day.is_past || new Date(day.calendar_date + "T00:00:00+08:00").getTime() + 86400000 <= currentTime,
    available_times: day.available_times.filter(time =>
      new Date(day.calendar_date + "T" + time + ":00+08:00").getTime() > currentTime),
  }));
  const byDate = new Map(days.map(day => [day.calendar_date, day]));
  const sortedDates = days.map(day => day.calendar_date).sort();
  const rangeStart = sortedDates[0];
  const rangeEnd = sortedDates[sortedDates.length - 1];
  const initialMonth = rangeStart ? rangeStart.slice(0, 7) : manilaToday().slice(0, 7);
  const [month, setMonth] = useState(initialMonth);
  useEffect(() => { setMonth(initialMonth); }, [initialMonth]);
  const monthStart = month + "-01";
  // Monday-based first cell of the displayed month (ISO weekday: Mon=1..Sun=7).
  const firstWeekday = new Date(monthStart + "T00:00:00").getDay();
  const leadingBlanks = (firstWeekday + 6) % 7;
  const monthDays = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate();
  const cellDates = Array.from({ length: leadingBlanks + monthDays }, (_, i) =>
    i < leadingBlanks ? null : month + "-" + String(i - leadingBlanks + 1).padStart(2, "0"));
  const today = manilaToday();
  // The loaded range spans ~30 days, so at most two adjacent months have data.
  const hasData = (m) => Boolean(rangeStart && rangeEnd && m >= rangeStart.slice(0, 7) && m <= rangeEnd.slice(0, 7));
  const shiftMonth = (delta) => {
    const next = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1 + delta, 1);
    setMonth(next.getFullYear() + "-" + String(next.getMonth() + 1).padStart(2, "0"));
  };
  const selectedDay = selected ? byDate.get(selected) : undefined;
  const monthTitle = new Date(monthStart + "T00:00:00").toLocaleDateString("en-PH", { month: "long", year: "numeric" });
  return <section className="rounded-xl border border-slate-200 bg-white p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{counselor ? "Counselor calendar" : "Available appointments"}</h2>
        <p className="mt-1 text-sm text-slate-500">{state.calendar?.business_hours || "Monday-Friday, 8:00 AM-4:00 PM"} · Philippine time</p></div>
      <div className="flex items-center gap-2">
        <span className="hidden rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 sm:inline">Live dates</span>
        <button type="button" aria-label="Previous month" disabled={!hasData(month) || month <= rangeStart.slice(0, 7)} onClick={() => shiftMonth(-1)} className={secondaryClass + " !px-2 !py-1"}>‹</button>
        <button type="button" aria-label="Next month" disabled={!hasData(month) || month >= rangeEnd.slice(0, 7)} onClick={() => shiftMonth(1)} className={secondaryClass + " !px-2 !py-1"}>›</button>
      </div>
    </div>
    <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="text-base font-medium">{monthTitle}</h3>
      <span className="text-xs text-slate-500">Showing loaded availability · times below update live</span>
    </div>
    <div className="mt-3 grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 text-center text-xs font-medium text-slate-500">
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <div key={d} className="bg-white py-2">{d}</div>)}
    </div>
    <div className="grid grid-cols-7 gap-px overflow-hidden rounded-b-lg border border-t-0 border-slate-200 bg-slate-200">
      {cellDates.map((cellDate, i) => {
        if (cellDate === null) return <div key={"blank" + i} className="min-h-20 bg-slate-50/50" />;
        const day = byDate.get(cellDate);
        const state2 = !day ? "outofrange" : day.is_past ? "past" : day.is_blocked ? "blocked" : !day.is_weekday ? "weekend" : "open";
        const bookable = day && !day.is_past && !day.is_blocked && day.is_weekday;
        const isToday = cellDate === today;
        const isSelected = cellDate === selected;
        const label = !day ? "" : day.is_past ? "Already passed" : day.is_blocked ? "Unavailable" : !day.is_weekday ? "Weekend" : day.available_times.length === 0 ? "No available time slots" : `${day.available_times.length} times available`;
        return <button key={cellDate} type="button" disabled={!bookable}
          onClick={() => { setSelected(cellDate); }}
          aria-label={cellDate + " — " + label}
          className={`group min-h-20 bg-white p-1.5 text-left transition-colors ${!bookable ? "cursor-default" : "hover:bg-emerald-50"} ${state2 === "past" ? "text-slate-300" : state2 === "blocked" ? "bg-red-50" : state2 === "weekend" ? "bg-slate-50 text-slate-400" : ""} ${isSelected ? "ring-2 ring-inset ring-emerald-600" : ""}`}>
          <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${isToday ? "bg-emerald-600 text-white" : ""}`}>{Number(cellDate.slice(8))}</span>
          {day && !day.is_past && day.is_weekday && !day.is_blocked && <p className="mt-1 hidden truncate text-[10px] font-medium text-emerald-700 sm:block">
            {day.available_times.length > 0 ? day.available_times.length + " open" : "No times left"}</p>}
          {day && (day.is_past || day.is_blocked || !day.is_weekday) && <p className="mt-1 hidden truncate text-[10px] text-slate-400 sm:block">{day.is_blocked ? "Blocked" : day.is_past ? "Passed" : "—"}</p>}
        </button>;
      })}
    </div>
    {selectedDay && !selectedDay.is_blocked && !selectedDay.is_past && <div className="mt-5 rounded-lg bg-slate-50 p-4"><p className="text-sm font-medium">Times for {selectedDay.calendar_date}</p>
      <div className="mt-3 flex flex-wrap gap-2">{selectedDay.available_times.map(time => <button key={time} type="button" className={secondaryClass} onClick={() => { state.setDate(selectedDay.calendar_date); }}>{time}</button>)}</div>
      {selectedDay.available_times.length === 0
        ? <p className="mt-3 text-sm text-amber-700">There are no available appointment time slots for this date. Please select another date.</p>
        : <p className="mt-3 text-xs text-slate-500">Select a time to filter the appointment list below.</p>}
    </div>}
    {counselor && <BlockDateForm state={state} />}
  </section>;
}

function BlockDateForm({ state }) {
  const [date, setDate] = useState(""); const [reason, setReason] = useState("");
  return <form className="mt-5 border-t border-slate-200 pt-5" onSubmit={async event => { event.preventDefault(); if (await state.mutate("/calendar/blocks", { blocked_date: date, reason: reason.trim() || null }, "POST", "Date blocked. Students can no longer request it.")) { setDate(""); setReason(""); } }}>
    <h3 className="font-medium">Block an unavailable date</h3><p className="mt-1 text-sm text-slate-500">Default face-to-face hours are Monday-Friday, 8:00 AM-4:00 PM.</p>
      <div className="mt-3 flex flex-wrap items-end gap-3"><label className="text-sm">Date<input className={inputClass} type="date" required min={manilaToday()} value={date} onChange={e => setDate(e.target.value)} /></label><label className="text-sm">Reason (optional)<input className={inputClass} maxLength={255} value={reason} onChange={e => setReason(e.target.value)} /></label><button className={buttonClass} disabled={state.busy}>Block date</button></div>
  </form>;
}

function WeeklyScheduleSection({ state }) {
  const [campusId, setCampusId] = useState("");
  const [day, setDay] = useState("1");
  const [start, setStart] = useState("08:00");
  const [end, setEnd] = useState("10:00");
  const [duration, setDuration] = useState("30");
  const [mode, setMode] = useState("ONLINE");
  const minutes = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
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
    {state.availabilityBlocks.length > 0 && <ul className="mt-5 space-y-2">
      {state.availabilityBlocks.map(b => <li key={b.availability_block_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm">
        <span>{formatSchedule(b.starts_at)} – {formatSchedule(b.ends_at)}{b.reason ? " · " + b.reason : ""}</span>
        <button className={secondaryClass} disabled={state.busy} onClick={() => void state.mutate("/availability-blocks/" + b.availability_block_id, undefined, "DELETE", "Unavailable time removed.")}>Remove</button>
      </li>)}
    </ul>}
  </section>;
}

function SlotCard({ slot, state, canBook, rescheduleId, onBooked }) {
  const [mode, setMode] = useState(slot.delivery_mode === "FACE_TO_FACE" ? "FACE_TO_FACE" : "ONLINE");
  const [, forceUpdate] = useState(0);
  const past = slotIsPast(slot);
  useEffect(() => {
    if (past) return;
    const remaining = new Date(slot.starts_at).getTime() - Date.now();
    const timer = setInterval(() => forceUpdate(n => n + 1), Math.min(30_000, Math.max(1000, remaining)));
    return () => clearInterval(timer);
  }, [slot.starts_at, past]);
  return <li className={`rounded-lg border p-4 ${past ? "border-slate-200 bg-slate-50 opacity-60" : "border-slate-200"}`}>
    <h3 className="font-medium">{formatSchedule(slot.starts_at)}</h3>
    <p className="text-sm text-slate-600">Until {formatSchedule(slot.ends_at)}</p>
    <p className="mt-2 text-sm">{slot.campus_name} · {slot.counselor_name}</p>
    <p className="text-sm text-slate-600">{modeLabel(slot.delivery_mode)} · {past ? "No longer available" : slot.status === "AVAILABLE" ? "Available" : "Reserved"}</p>
    {slot.delivery_mode !== "FACE_TO_FACE" && <p className="mt-1 text-sm text-slate-600">Online sessions cannot be joined in the app yet.</p>}
    {slot.delivery_mode !== "ONLINE" && <p className="mt-1 text-sm text-slate-600">Guidance Office: {slot.guidance_office_location || "Not configured"}</p>}
    {past && <p className="mt-1 text-sm text-amber-700">This appointment time is no longer available. Please select another available time.</p>}
    {canBook && slot.status === "AVAILABLE" && !past && <form className="mt-3 flex flex-wrap items-end gap-3" onSubmit={async e => {
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

function AppointmentCard({ appointment: a, state, counselor, onReschedule }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const action = (name, body) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
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

export default function AppointmentsPage({ user }) {
  const state = useAppointments(user.role_code);
  const counselor = user.role_code === "COUNSELOR";
  const [rescheduleId, setRescheduleId] = useState(null);
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
          <label className="text-sm">Date<input className={inputClass} disabled={state.busy} type="date" min={manilaToday()} value={state.date} onChange={e => { state.setDate(e.target.value >= manilaToday() ? e.target.value : ""); state.setSlotPage(1); }} /></label>
          <label className="text-sm">Mode<select className={inputClass} disabled={state.busy} value={state.mode} onChange={e => { state.setMode(e.target.value); state.setSlotPage(1); }}>
            <option value="">All modes</option><option value="ONLINE">Online</option><option value="FACE_TO_FACE">Face-to-face</option>
          </select></label>
        </div>
        {state.loading ? <p role="status" className="mt-4">Loading appointments…</p> : <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {state.slots.items.map(slot => <SlotCard key={slot.slot_id + ":" + slot.delivery_mode} slot={slot} state={state} canBook={!counselor || rescheduleId !== null} rescheduleId={rescheduleId} onBooked={() => setRescheduleId(null)} />)}
        </ul>}
        {!state.loading && !state.error && state.slots.items.length === 0 && <p className="mt-4 text-sm text-slate-500">{state.date
          ? "There are no available appointment time slots for this date. Please select another date."
          : "No slots match these filters."}</p>}
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
