import { useEffect, useState } from "react";
import { formatSchedule } from "../features/appointments";
import SessionRecordWorkspace from "../components/sessionRecords/SessionRecordWorkspace";
import { request } from "../services/apiClient";

/** Standalone session workspace for face-to-face sessions and post-call work. */
export default function SessionRecordPage({ user, appointmentId }) {
  const [appointment, setAppointment] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    request(`/appointments/${appointmentId}`)
      .then(data => { if (!cancelled) { setAppointment(data); setError(""); } })
      .catch(err => { if (!cancelled) setError(err.message); });
    return () => { cancelled = true; };
  }, [appointmentId]);

  if (error) return <main className="p-6"><p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{error}</p></main>;
  if (!appointment) return <main className="p-6"><p role="status">Loading session…</p></main>;

  const other = user.role_code === "COUNSELOR" ? appointment.student_name : appointment.counselor_name;
  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6 lg:h-[100dvh] lg:overflow-hidden">
    <div className="mx-auto max-w-5xl space-y-6 lg:flex lg:h-full lg:min-h-0 lg:flex-col">
      <header className="shrink-0 space-y-1">
        <a href="#appointments" className="text-sm font-medium text-emerald-700">← Back</a>
        <h1 className="text-2xl font-bold text-[#207524]">Session record</h1>
        <p className="text-sm text-slate-500">
          {user.role_code === "COUNSELOR" ? "Student: " + other : "Counselor: " + other}
          {" · "}{formatSchedule(appointment.starts_at)} to {formatSchedule(appointment.ends_at)}
          {" · "}{appointment.campus_name}
        </p>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{appointment.appointment_mode.replaceAll("_", "-")} · {appointment.status.replaceAll("_", " ")}</p>
      </header>
      <div className="flex max-h-[80dvh] flex-col overflow-hidden rounded-2xl border border-[#E9EDF1] bg-white p-6 shadow-sm lg:max-h-none lg:min-h-0 lg:flex-1">
        <SessionRecordWorkspace user={user} appointment={appointment} scrollable />
      </div>
    </div>
  </main>;
}
