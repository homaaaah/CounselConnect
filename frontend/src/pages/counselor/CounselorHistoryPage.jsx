import { useState } from "react";
import { useAppointments, formatSchedule } from "../../features/appointments";
import { buttonClass, secondaryClass, modeLabel } from "../../components/appointments/ui";
import BookingModal from "../../components/appointments/BookingModal.jsx";

function Pagination({ page, total, onChange, disabled }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function RecordCard({ appointment: a, state, onReschedule }) {
  const [cancelling, setCancelling] = useState(false);
  const action = (name, body) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
  const started = new Date(a.starts_at).getTime() <= Date.now();
  const canCancel = a.can_cancel ?? (a.status === "CONFIRMED");
  const canReschedule = a.can_reschedule ?? (a.status === "CONFIRMED" && a.conversation_id === null);
  const canChangeMode = a.can_change_mode ?? false;
  return <li className="rounded-lg border border-slate-200 p-5">
    <div className="flex flex-wrap justify-between gap-2">
      <h3 className="font-semibold">{formatSchedule(a.starts_at)}</h3>
      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{a.status.replaceAll("_", " ")}</span>
    </div>
    <p className="text-sm text-slate-500">Until {formatSchedule(a.ends_at)} · {a.campus_name}</p>
    <p className="mt-3 text-sm">{"Student: " + a.student_name}</p>
    <p className="text-sm">{modeLabel(a.appointment_mode)}</p>
    {a.meeting_location && <p className="mt-1 text-sm">Guidance Office: {a.meeting_location}</p>}
    {a.rejection_note && <p className="mt-2 text-sm text-slate-600">Counselor note: {a.rejection_note}</p>}
    {a.status === "CONFIRMED" && <p className="mt-2 text-sm text-slate-600">A completed session is marked here; report contents are not part of the frontend records view.</p>}
    <div className="mt-4 flex flex-wrap gap-2">
      {canCancel && <button className={secondaryClass} disabled={state.busy} onClick={() => setCancelling(!cancelling)}>Cancel appointment</button>}
      {canReschedule && <button className={secondaryClass} disabled={state.busy} onClick={() => onReschedule(a.appointment_id)}>Reschedule</button>}
      {canChangeMode && <button className={secondaryClass} disabled={state.busy} onClick={() => void action("change-mode", { appointment_mode: a.appointment_mode === "ONLINE" ? "FACE_TO_FACE" : "ONLINE" })}>Change to {a.appointment_mode === "ONLINE" ? "face-to-face" : "online"}</button>}
      {a.status === "CONFIRMED" && <>
        <button className={buttonClass} disabled={state.busy || !started} onClick={() => void action("complete")}>Mark completed</button>
        <button className={secondaryClass} disabled={state.busy || !started} onClick={() => void action("no-show")}>Mark no-show</button>
      </>}
    </div>
    {cancelling && canCancel && <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm">
      <p>Cancel this appointment and release the slot?</p>
      <button className={secondaryClass + " mt-2"} disabled={state.busy} onClick={async () => { if (await action("cancel")) setCancelling(false); }}>Confirm cancellation</button>
    </div>}
  </li>;
}

const RECORD_STATUSES = ["CONFIRMED", "COMPLETED", "NO_SHOW", "CANCELLED", "REJECTED"];
const statusLabel = (status) => status === "NO_SHOW" ? "No-show" : status.charAt(0) + status.slice(1).toLowerCase();

function HistoryToolbar({ state, query, setQuery }) {
  const [open, setOpen] = useState(false);
  return <div className="relative flex items-center gap-2">
    <label className="flex items-center gap-2 rounded-lg border border-[#E9EDF1] bg-white px-3 py-2 text-sm">
      <i className="fa-solid fa-magnifying-glass text-[#B1B8C2]" aria-hidden="true"></i>
      <span className="sr-only">Search session history</span>
      <input className="w-40 bg-transparent outline-none" placeholder="Search" value={query} onChange={e => setQuery(e.target.value)} />
    </label>
    <button type="button" aria-expanded={open} aria-haspopup="true" aria-label={"Filter session history" + (state.status ? ", " + statusLabel(state.status) : "")}
      className={"rounded-lg border px-3 py-2 " + (state.status
        ? "border-[#207524] text-[#207524]"
        : "border-[#E9EDF1] text-slate-600 hover:bg-slate-50")}
      onClick={() => setOpen(!open)}>
      <i className="fa-solid fa-filter" aria-hidden="true"></i>
    </button>
    {open && <div role="menu" aria-label="Filter by status" className="absolute right-0 top-11 z-20 w-44 rounded-lg border border-[#E9EDF1] bg-white p-1 shadow-lg">
      {RECORD_STATUSES.map(status => <button key={status} type="button" role="menuitemradio" aria-checked={state.status === status}
        className={"block w-full rounded-md px-3 py-2 text-left text-sm " + (state.status === status ? "bg-emerald-50 font-medium text-[#207524]" : "text-slate-700 hover:bg-slate-50")}
        onClick={() => { state.setStatus(status); state.setAppointmentPage(1); setOpen(false); }}>{statusLabel(status)}</button>)}
    </div>}
  </div>;
}

/**
 * Counselor "History" page — previous counseling records (confirmed, completed,
 * no-show, cancelled, rejected) with their lifecycle actions. Moved off the
 * Appointments page, which now only reviews pending requests.
 */
export default function CounselorHistoryPage({ user }) {
  const state = useAppointments(user.role_code, "CONFIRMED");
  const [rescheduleId, setRescheduleId] = useState(null);
  const [query, setQuery] = useState("");
  const term = query.trim().toLowerCase();
  const visible = term
    ? state.appointments.items.filter(a => (a.student_name ?? "").toLowerCase().includes(term))
    : state.appointments.items;
  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#207524]">History</h1>
          <p className="mt-1 text-sm text-slate-500">Review and manage previous counseling of your students.</p>
        </div>
        <button className={secondaryClass} disabled={state.busy || state.loading} onClick={() => void state.refresh()}>Refresh</button>
      </header>
      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving...</p>}

      <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-lg font-semibold">Student records</h2>
          <HistoryToolbar state={state} query={query} setQuery={setQuery} />
        </div>
        {state.recordsError && <p role="alert" className="mt-4 text-sm text-red-700">{state.recordsError}</p>}
        {!state.recordsLoading && <ul className="mt-4 space-y-4">{visible.map(a =>
          <RecordCard key={a.appointment_id} appointment={a} state={state} onReschedule={setRescheduleId} />)}</ul>}
        {!state.recordsLoading && !state.recordsError && visible.length === 0 &&
          <p className="mt-4 text-sm text-slate-500">{term
            ? "No records match your search."
            : "No " + (state.status ? state.status.replaceAll("_", " ").toLowerCase() : "") + " student appointments yet."}</p>}
        <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.recordsLoading} />
      </section>

      <BookingModal open={rescheduleId !== null} onClose={() => setRescheduleId(null)} state={state} rescheduleId={rescheduleId}
        selfCounselorId={user.user_id} selfCounselorName={`${user.first_name} ${user.last_name}`} />
    </div>
  </main>;
}
