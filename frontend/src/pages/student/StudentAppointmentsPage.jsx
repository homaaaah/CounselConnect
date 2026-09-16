import { useState } from "react";
import { useAppointments, formatSchedule } from "../../features/appointments";
import { buttonClass, secondaryClass, inputClass, modeLabel } from "../../components/appointments/ui.js";
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

function RecordsTabs({ state }) {
  const recordsTabs = ["CONFIRMED", "PENDING", "COMPLETED"];
  const tabLabel = (s) => s.charAt(0) + s.slice(1).toLowerCase();
  return <div role="tablist" aria-label="Filter records by status" className="flex flex-wrap gap-2">
    {recordsTabs.map(s => <button key={s} type="button" role="tab" aria-selected={state.status === s}
      className={state.status === s
        ? "rounded-md bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white"
        : "rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"}
      onClick={() => { state.setStatus(s); state.setAppointmentPage(1); }}>{tabLabel(s)}</button>)}
  </div>;
}

export default function StudentAppointmentsPage({ user }) {
  const state = useAppointments(user.role_code, "CONFIRMED");
  const [rescheduleId, setRescheduleId] = useState(null);
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold">My appointments</h1>
        <p className="mt-1 text-sm text-slate-500">Your confirmed, pending, and completed guidance sessions. Philippine time (Asia/Manila).</p>
        <button className={secondaryClass + " mt-3"} disabled={state.busy || state.loading} onClick={() => void state.refresh()}>Refresh records</button>
      </header>
      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving…</p>}

      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-lg font-semibold">Your records</h2>
          <RecordsTabs state={state} />
        </div>
        {state.recordsError && <p role="alert" className="mt-4 text-sm text-red-700">{state.recordsError}</p>}
        {!state.recordsLoading && <ul className="mt-4 space-y-4">{state.appointments.items.map(a =>
          <AppointmentCard key={a.appointment_id} appointment={a} state={state} counselor={false} onReschedule={setRescheduleId} />)}</ul>}
        {!state.recordsLoading && !state.recordsError && state.appointments.items.length === 0 &&
          <p className="mt-4 text-sm text-slate-500">No {state.status ? state.status.replaceAll("_", " ").toLowerCase() : ""} appointments yet. Use Schedule on the homepage to request one.</p>}
        <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.recordsLoading} />
      </section>

      <BookingModal open={rescheduleId !== null} onClose={() => setRescheduleId(null)} state={state} rescheduleId={rescheduleId} />
    </div>
  </main>;
}
