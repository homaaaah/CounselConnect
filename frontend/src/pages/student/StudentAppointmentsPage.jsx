import { useState } from "react";
import { useAppointments, formatSchedule } from "../../features/appointments";
import { secondaryClass, modeLabel } from "../../components/appointments/ui.js";
import BookingModal from "../../components/appointments/BookingModal.jsx";
import ConcernSummary from "../../components/appointments/ConcernSummary.jsx";

function Pagination({ page, total, onChange, disabled }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}
function AppointmentCard({ appointment: a, state, onReschedule }) {
  const [cancelling, setCancelling] = useState(false);
  const action = (name, body) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
  const active = a.status === "PENDING" || a.status === "CONFIRMED";
  const canCancel = a.can_cancel ?? active;
  const canReschedule = a.can_reschedule ?? (a.status === "CONFIRMED" && a.conversation_id === null);
  return <li className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <div className="flex flex-wrap justify-between gap-2">
      <h3 className="font-semibold text-slate-900">{formatSchedule(a.starts_at)}</h3>
      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">{a.status.replaceAll("_", " ")}</span>
    </div>
    <p className="text-sm text-slate-500 mt-1">Until {formatSchedule(a.ends_at)} · {a.campus_name}</p>
    <p className="mt-3 text-sm font-medium text-slate-800">Counselor: {a.counselor_name}</p>
    <p className="text-sm text-slate-600">{modeLabel(a.appointment_mode)}</p>
    {a.meeting_location && <p className="mt-1 text-sm text-slate-600">Guidance Office: {a.meeting_location}</p>}
    <ConcernSummary categories={a.concern_categories} details={a.concern_details} className="mt-3 rounded-lg bg-slate-50 p-3" />
    {a.rejection_note && <p className="mt-2 text-sm text-slate-600">Counselor note: {a.rejection_note}</p>}
    {a.status === "PENDING" && <p className="mt-2 text-sm text-amber-700">Awaiting counselor review.</p>}
    {a.status === "CONFIRMED" && a.appointment_mode === "ONLINE" && <p className="mt-2 text-sm text-slate-600">Online appointment confirmed. The session lobby opens 30 minutes before the scheduled start.</p>}
    <div className="mt-4 flex flex-wrap gap-2">
      {["CONFIRMED", "COMPLETED"].includes(a.status) && (a.status === "COMPLETED"
        ? <a className={secondaryClass} href={"#session-record/" + a.appointment_id}>Session files</a>
        : <span aria-disabled="true" title="Available after the session is completed" className={secondaryClass + " cursor-not-allowed opacity-50"}>Session files</span>)}
      {canCancel && <button className={secondaryClass} disabled={state.busy} onClick={() => setCancelling(!cancelling)}>Cancel appointment</button>}
      {canReschedule && <button className={secondaryClass} disabled={state.busy} onClick={() => onReschedule(a.appointment_id)}>Reschedule</button>}
    </div>
    {cancelling && canCancel && <div className="mt-3 rounded-md bg-amber-50 p-3 text-sm">
      <p>Cancel this appointment and release the slot?</p>
      <button className={secondaryClass + " mt-2"} disabled={state.busy} onClick={async () => { if (await action("cancel")) setCancelling(false); }}>Confirm cancellation</button>
    </div>}
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
        ? "rounded-full bg-emerald-700 px-4 py-2 text-sm font-medium text-white shadow-sm"
        : "rounded-full border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"}
      onClick={() => { state.setStatus(status); state.setAppointmentPage(1); }}>{label}</button>)}
  </div>;
}

export default function StudentAppointmentsPage({ user }) {
  const state = useAppointments(user.role_code, "CONFIRMED");
  const [rescheduleId, setRescheduleId] = useState(null);
  const [bookingOpen, setBookingOpen] = useState(false);

  return <main className="min-h-screen bg-white px-4 py-8 text-slate-800 sm:px-6 lg:px-8">
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Page Header (Reference Image 2) */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">My Appointments</h1>
          <p className="mt-1 text-sm text-slate-600">Manage your upcoming and past counseling sessions.</p>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-full bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-800 transition-colors"
          onClick={() => setBookingOpen(true)}
        >
          <i className="fa-solid fa-calendar-plus" aria-hidden="true"></i> Schedule Appointment
        </button>
      </div>

      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving…</p>}

      <section className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <RecordsTabs state={state} />
          <button className={secondaryClass} disabled={state.busy || state.loading} onClick={() => void state.refresh()}>Refresh records</button>
        </div>

        {state.recordsError && <p role="alert" className="mt-4 text-sm text-red-700">{state.recordsError}</p>}

        {!state.recordsLoading && state.appointments.items.length > 0 && (
          <ul className="space-y-4">
            {state.appointments.items.map(a =>
              <AppointmentCard key={a.appointment_id} appointment={a} state={state} onReschedule={setRescheduleId} />)}
          </ul>
        )}

        {/* Empty State (Reference Image 2) */}
        {!state.recordsLoading && !state.recordsError && state.appointments.items.length === 0 && (
          <div className="rounded-3xl border-2 border-dashed border-slate-200 bg-slate-50/50 p-12 text-center space-y-4">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 text-emerald-700 text-2xl">
              <i className="fa-regular fa-calendar" aria-hidden="true"></i>
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-bold text-slate-900">No appointments scheduled yet</h2>
              <p className="text-sm text-slate-500 max-w-sm mx-auto">
                You haven't scheduled any {state.status ? state.status.replaceAll("_", " ").toLowerCase() : ""} counseling sessions. Get started by finding a counselor.
              </p>
            </div>
            <div className="pt-2 flex flex-wrap justify-center gap-3">
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-full bg-emerald-700 px-6 py-3 text-sm font-semibold text-white shadow hover:bg-emerald-800 transition-colors"
                onClick={() => setBookingOpen(true)}
              >
                Find a Counselor
              </button>
            </div>
            <div className="pt-2 flex justify-center gap-4 text-xs text-slate-500">
              <a href="#appointments" className="hover:underline">View History</a>
              <span>·</span>
              <a href="#landing" className="hover:underline">How it works</a>
            </div>
          </div>
        )}

        <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.recordsLoading} />
      </section>

      <BookingModal open={rescheduleId !== null || bookingOpen} onClose={() => { setRescheduleId(null); setBookingOpen(false); }} state={state} rescheduleId={rescheduleId} />
    </div>
  </main>;
}
