import { useEffect, useRef, useState } from "react";
import { useAppointments } from "../../features/appointments";
import { buttonClass, secondaryClass, inputClass } from "../../components/appointments/ui";
import ConcernSummary from "../../components/appointments/ConcernSummary.jsx";

const MANILA = "Asia/Manila";
const dateLabel = (value) => new Intl.DateTimeFormat("en-PH", { timeZone: MANILA, month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
const timeLabelOf = (value) => new Intl.DateTimeFormat("en-PH", { timeZone: MANILA, hour: "numeric", minute: "2-digit" }).format(new Date(value));
const modeLabelOf = (mode) => mode === "ONLINE" ? "Online Call" : "Face-to-face";
const initialsOf = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0].toUpperCase()).join("");
const durationLabel = (a) => {
  const minutes = Math.round((new Date(a.ends_at) - new Date(a.starts_at)) / 60000);
  return minutes > 0 ? ` (${minutes}m)` : "";
};

function Pagination({ page, total, onChange, disabled }) {
  return <div className="mt-4 flex items-center justify-between gap-3 text-sm">
    <button className={secondaryClass} disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
    <span>Page {page} of {Math.max(1, Math.ceil(total / 20))}</span>
    <button className={secondaryClass} disabled={disabled || page * 20 >= total} onClick={() => onChange(page + 1)}>Next</button>
  </div>;
}

function MetadataColumn({ icon, label, value }) {
  return <div className="flex items-center gap-2">
    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white text-[#207524] shadow-sm">
      <i className={"fa-solid " + icon} aria-hidden="true"></i>
    </span>
    <span className="min-w-0">
      <span className="block text-[10px] font-semibold uppercase tracking-wide text-[#7B8493]">{label}</span>
      <span className="block truncate text-sm font-semibold text-slate-700">{value}</span>
    </span>
  </div>;
}

function PendingRequestCard({ appointment: a, state, open, onToggle }) {
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const action = (name, body) => state.mutate("/appointments/" + a.appointment_id + "/" + name, body);
  const started = new Date(a.starts_at).getTime() <= Date.now();
  const detailsId = `request-details-${a.appointment_id}`;
  return <li className={"rounded-2xl border bg-white p-4 " + (open ? "border-[#21812B]" : "border-[#E9EDF1]")}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-center gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-sm font-semibold text-[#207524]">{initialsOf(a.student_name)}</span>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-bold text-slate-800">{a.student_name ?? "—"}</h3>
          <p className="text-xs text-[#7B8493]">{a.campus_name}</p>
        </div>
      </div>
      <span className="rounded-full bg-[#FFFAEB] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[#D97724]">Pending review</span>
    </div>

    <div className="mt-3 flex items-center gap-3 rounded-xl bg-[#F8FAFB] px-3 py-2">
      <div className="grid flex-1 gap-2 sm:grid-cols-3">
        <MetadataColumn icon="fa-calendar" label="Date" value={dateLabel(a.starts_at)} />
        <MetadataColumn icon="fa-clock" label="Time" value={timeLabelOf(a.starts_at) + durationLabel(a)} />
        <MetadataColumn icon="fa-location-dot" label="Mode" value={modeLabelOf(a.appointment_mode)} />
      </div>
      <button type="button" aria-expanded={open} aria-controls={detailsId}
        aria-label={(open ? "Collapse" : "Expand") + " request from " + (a.student_name ?? "student")}
        className="rounded-md p-2 text-[#207524] hover:bg-white" onClick={onToggle}>
        <i className={"fa-solid " + (open ? "fa-chevron-up" : "fa-chevron-down")} aria-hidden="true"></i>
      </button>
    </div>

    <div id={detailsId} hidden={!open} className="mt-3 space-y-3">
      <ConcernSummary categories={a.concern_categories} details={a.concern_details} className="rounded-xl bg-emerald-50 p-3" />
      <div className="rounded-xl border-l-4 border-[#D8EAD8] bg-[#F8FAFB] p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-[#7B8493]">Request</p>
        <p className="text-sm text-slate-600">
          Requested {a.appointment_mode === "ONLINE" ? "an online call" : "a face-to-face session"} at {a.campus_name}.
          {a.meeting_location ? " Guidance Office: " + a.meeting_location + "." : ""}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className={buttonClass} disabled={state.busy || started} onClick={() => void action("confirm")}>
          <i className="fa-solid fa-check mr-2" aria-hidden="true"></i>Accept Appointment
        </button>
        <button className={secondaryClass + " ml-auto"} disabled={state.busy} onClick={() => setRejecting(!rejecting)}>Reject</button>
      </div>
      {rejecting && <form className="rounded-lg bg-slate-50 p-3" onSubmit={async e => {
        e.preventDefault(); if (await action("reject", { rejection_note: note.trim() || null })) { setRejecting(false); setNote(""); }
      }}>
        <label className="text-sm">Reason (optional)<textarea className={inputClass} maxLength={500} value={note} onChange={e => setNote(e.target.value)} /></label>
        <button className={secondaryClass + " mt-2"} disabled={state.busy}>Reject request</button>
      </form>}
    </div>
  </li>;
}

/**
 * Counselor "Appointment Requests" page — reviews pending student booking
 * requests and accepts or rejects them. Availability configuration lives on
 * the Schedule page; other counseling records live on the History page.
 * (design/CounselConnect_Appointment_Requests_UI_Spec.md)
 */
export default function CounselorAppointmentsPage({ user }) {
  const state = useAppointments(user.role_code, "PENDING");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState(null);
  const seeded = useRef(false);
  const items = state.appointments.items;

  useEffect(() => {
    if (!seeded.current && items.length) { seeded.current = true; setOpenId(items[0].appointment_id); }
  }, [items]);

  const term = query.trim().toLowerCase();
  const visible = term ? items.filter(a => (a.student_name ?? "").toLowerCase().includes(term)) : items;

  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[#207524]">Appointment Requests</h1>
          <p className="mt-1 text-sm text-slate-500">Review and manage incoming booking requests from your students.</p>
        </div>
        <label className="flex items-center gap-2 rounded-lg border border-[#E9EDF1] bg-white px-3 py-2 text-sm">
          <i className="fa-solid fa-magnifying-glass text-[#B1B8C2]" aria-hidden="true"></i>
          <span className="sr-only">Search appointment requests</span>
          <input className="w-40 bg-transparent outline-none" placeholder="Search" value={query} onChange={e => setQuery(e.target.value)} />
        </label>
      </header>

      {state.error && <p role="alert" className="rounded-lg bg-red-50 p-4 text-red-700">{state.error}</p>}
      {state.message && <p role="status" className="rounded-lg bg-emerald-50 p-4 text-emerald-800">{state.message}</p>}
      {state.busy && <p role="status">Saving...</p>}

      {state.recordsError && <p role="alert" className="text-sm text-red-700">{state.recordsError}</p>}
      {state.recordsLoading
        ? <p role="status" className="text-sm text-slate-500">Loading requests...</p>
        : <ul className="space-y-2">
          {visible.map(a => <PendingRequestCard key={a.appointment_id} appointment={a} state={state}
            open={openId === a.appointment_id} onToggle={() => setOpenId(openId === a.appointment_id ? null : a.appointment_id)} />)}
        </ul>}
      {!state.recordsLoading && !state.recordsError && visible.length === 0 &&
        <p className="rounded-xl border border-[#E9EDF1] bg-white p-6 text-sm text-slate-500">
          {term ? "No requests match your search." : "No pending appointment requests right now."}
        </p>}

      <Pagination page={state.appointmentPage} total={state.appointments.total} onChange={state.setAppointmentPage} disabled={state.busy || state.recordsLoading} />
    </div>
  </main>;
}
