import { formatSchedule } from "../../features/appointments";
import { modeLabel } from "../../components/appointments/ui.js";
import { useCounselorDashboard } from "../../features/counselor";

/**
 * Counselor dashboard.
 *
 * Layout mirrors the approved design: a welcome banner with the day's summary,
 * four metric cards, today's appointment list, a weekly volume line chart, a
 * case-distribution donut, and an availability-update action.
 *
 * No values are hard-coded. Everything is read from useCounselorDashboard;
 * widgets whose source does not exist yet render an empty state while keeping
 * their container visible, so they populate automatically once data is wired.
 */

const WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const CASE_COLORS = ["#1C6B1B", "#409e44", "#a7d7a8", "#cbd5e1"];

const STATUS_META = {
  COMPLETED: { label: "Completed", icon: "fa-circle-check", className: "bg-emerald-50 text-emerald-700" },
  CONFIRMED: { label: "Confirmed", icon: "fa-circle-check", className: "bg-blue-50 text-blue-700" },
  PENDING: { label: "Pending", icon: "fa-clock", className: "bg-amber-50 text-amber-700" },
  NO_SHOW: { label: "No-show", icon: "fa-circle-xmark", className: "bg-slate-100 text-slate-600" },
  CANCELLED: { label: "Cancelled", icon: "fa-circle-xmark", className: "bg-slate-100 text-slate-600" },
  REJECTED: { label: "Rejected", icon: "fa-circle-xmark", className: "bg-red-50 text-red-700" },
};

const initials = (name) =>
  (name ?? "").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "?";

function EmptyState({ text }) {
  return <p className="rounded-2xl border border-dashed border-[#E9EDF1] bg-slate-50 p-6 text-center text-sm text-slate-500">{text}</p>;
}

function StatCard({ label, value, loading, icon, urgent, href }) {
  const body = <>
    <div className="flex items-start justify-between">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-50 text-emerald-700">
        <i className={"fa-solid " + icon} aria-hidden="true"></i>
      </span>
      {urgent && <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-red-700">Action needed</span>}
    </div>
    <p className="mt-3 text-2xl font-bold text-slate-900">{loading ? "..." : value ?? "—"}</p>
    <p className="text-xs text-slate-500">{label}</p>
  </>;
  const shell = "flex h-full flex-col rounded-2xl border border-[#E9EDF1] bg-white p-4";
  return href
    ? <a href={href} className={shell + " transition-shadow hover:shadow-sm"}>{body}</a>
    : <div className={shell}>{body}</div>;
}

function StatusBadge({ status }) {
  const meta = STATUS_META[status] ?? {
    label: (status ?? "").replaceAll("_", " "), icon: "fa-circle-info", className: "bg-slate-100 text-slate-600",
  };
  return <span className={"inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold " + meta.className}>
    <i className={"fa-solid " + meta.icon} aria-hidden="true"></i>{meta.label}
  </span>;
}

function WelcomeBanner({ user, today }) {
  const hour = Number(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Manila", hour: "2-digit", hour12: false,
  }).format(new Date()));
  const salutation = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const count = today.items.length;
  const pending = today.items.filter((appointment) => appointment.status === "PENDING").length;
  const summary = [];
  if (count) summary.push(`${count} appointment${count === 1 ? "" : "s"} today`);
  if (pending) summary.push(`${pending} awaiting your review`);
  const subtitle = summary.length
    ? summary.join(" · ") + "."
    : "Here's your Guidance Office overview for today.";

  return <section
    className="relative overflow-hidden rounded-2xl p-6 text-white sm:p-8"
    style={{ background: "linear-gradient(135deg, #1C6B1B 0%, #14511a 60%, #0f3d14 100%)" }}
  >
    <div
      className="pointer-events-none absolute inset-0 opacity-40"
      style={{ backgroundImage: "radial-gradient(circle at 15% 20%, rgba(255,255,255,0.18) 0, transparent 35%), radial-gradient(circle at 85% 80%, rgba(255,255,255,0.12) 0, transparent 40%)" }}
      aria-hidden="true"
    ></div>
    <div className="relative">
      <h1 className="text-2xl font-bold sm:text-3xl">{salutation}, {user.first_name}.</h1>
      <p className="mt-2 max-w-xl text-sm text-emerald-50">{subtitle}</p>
    </div>
  </section>;
}

function TodayAppointments({ today }) {
  return <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6">
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-base font-semibold text-slate-900">Today's appointments</h2>
      <a href="#history" className="text-sm font-semibold text-emerald-700 hover:underline">View Schedule</a>
    </div>
    {today.error && <p role="alert" className="mt-3 text-sm text-red-700">{today.error}</p>}
    {today.loading
      ? <p role="status" className="mt-4 text-sm text-slate-500">Loading today's appointments…</p>
      : today.items.length === 0
        ? <div className="mt-4"><EmptyState text="No appointments scheduled for today." /></div>
        : <ul className="mt-4 space-y-3">
          {today.items.map((appointment) => <li key={appointment.appointment_id}
            className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-100 p-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-sm font-semibold text-emerald-700">
              {initials(appointment.student_name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">{appointment.student_name ?? "—"}</p>
              <p className="text-xs text-slate-500">{formatSchedule(appointment.starts_at)}</p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
              {modeLabel(appointment.appointment_mode)}
            </span>
            <StatusBadge status={appointment.status} />
          </li>)}
        </ul>}
  </section>;
}

function AvailabilityWidget() {
  return <section className="flex h-full flex-col rounded-2xl border border-[#E9EDF1] bg-white p-6">
    <h2 className="text-base font-semibold text-slate-900">Availability update</h2>
    <p className="mt-1 text-sm text-slate-500">Set the open slots students can book for the upcoming week.</p>
    <div className="mt-auto pt-5">
      <a href="#schedule"
        className="inline-flex items-center gap-2 rounded-full bg-[#1C6B1B] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#175317]">
        Manage Schedule <i className="fa-solid fa-arrow-right" aria-hidden="true"></i>
      </a>
    </div>
  </section>;
}

function WeeklyVolumeChart({ data }) {
  if (!data || !Array.isArray(data.myCases) || data.myCases.length === 0) {
    return <EmptyState text="No weekly appointment volume yet." />;
  }
  const width = 520, height = 200, pad = 28;
  const series = [data.myCases, data.centerAverage].filter((values) => Array.isArray(values));
  const max = Math.max(1, ...series.flat());
  const stepX = (width - pad * 2) / Math.max(1, data.myCases.length - 1);
  const toPoints = (values) => values
    .map((value, index) => `${pad + index * stepX},${height - pad - (value / max) * (height - pad * 2)}`)
    .join(" ");
  return <svg viewBox={`0 0 ${width} ${height}`} className="h-48 w-full" role="img" aria-label="Weekly appointment volume">
    {Array.isArray(data.centerAverage) && <polyline points={toPoints(data.centerAverage)} fill="none" stroke="#94a3b8" strokeWidth="2" strokeDasharray="6 4" />}
    <polyline points={toPoints(data.myCases)} fill="none" stroke="#1C6B1B" strokeWidth="2.5" />
    {WEEK_DAYS.slice(0, data.myCases.length).map((day, index) => (
      <text key={day} x={pad + index * stepX} y={height - 8} textAnchor="middle" fontSize="10" className="fill-slate-400">{day}</text>
    ))}
  </svg>;
}

function CaseDistributionChart({ segments }) {
  if (!segments || segments.length === 0) return <EmptyState text="No case distribution data yet." />;
  const total = segments.reduce((sum, segment) => sum + segment.value, 0) || 1;
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  let running = 0;
  const arcs = segments.map((segment, index) => {
    const dash = (segment.value / total) * circumference;
    const arc = { ...segment, index, dash, offset: running };
    running += dash;
    return arc;
  });
  return <div className="flex flex-wrap items-center gap-5">
    <svg viewBox="0 0 140 140" className="h-36 w-36" role="img" aria-label="Case distribution">
      <g transform="rotate(-90 70 70)">
        {arcs.map((arc) => <circle key={arc.label} cx="70" cy="70" r={radius} fill="none"
          stroke={arc.color ?? CASE_COLORS[arc.index % CASE_COLORS.length]}
          strokeWidth="18" strokeDasharray={`${arc.dash} ${circumference - arc.dash}`} strokeDashoffset={-arc.offset} />)}
      </g>
    </svg>
    <ul className="space-y-2 text-sm">
      {arcs.map((arc) => <li key={arc.label} className="flex items-center gap-2">
        <span className="h-3 w-3 rounded-full" style={{ background: arc.color ?? CASE_COLORS[arc.index % CASE_COLORS.length] }}></span>
        <span className="text-slate-600">{arc.label}</span>
        <span className="font-semibold text-slate-900">{Math.round((arc.value / total) * 100)}%</span>
      </li>)}
    </ul>
  </div>;
}

export default function CounselorDashboard({ user }) {
  const dash = useCounselorDashboard(user);
  const pending = dash.pendingRequests.total;
  const metrics = [
    { key: "appointments", label: "Appointments", icon: "fa-calendar-check", value: dash.appointments.total, loading: dash.appointments.loading },
    { key: "pending", label: "Pending Requests", icon: "fa-clock", value: pending, loading: dash.pendingRequests.loading, urgent: (pending ?? 0) > 0, href: "#appointments" },
    { key: "solved", label: "Solved Cases", icon: "fa-clipboard-check", value: dash.solvedCases },
    { key: "ongoing", label: "On-going", icon: "fa-hourglass-half", value: dash.ongoingCases },
  ];
  const caseSegments = dash.caseDistribution ?? [];

  return <main className="min-h-screen bg-[#F7F9FB] px-4 py-8 text-slate-800 sm:px-6">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          {/* h2: the welcome banner owns the page's single h1. */}
          <h2 className="text-2xl font-bold text-[#207524]">Dashboard</h2>
          <p className="mt-1 text-sm text-slate-500">Guidance Office overview. Philippine time (Asia/Manila).</p>
        </div>
      </header>

      {dash.appointments.error && <p role="alert" className="text-sm text-red-700">{dash.appointments.error}</p>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><WelcomeBanner user={user} today={dash.today} /></div>
        <div className="grid grid-cols-2 gap-6 lg:col-span-1">
          {metrics.map(({ key, ...metric }) => <StatCard key={key} {...metric} />)}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2"><TodayAppointments today={dash.today} /></div>
        <div className="lg:col-span-1"><AvailabilityWidget /></div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6 lg:col-span-2">
          <h2 className="text-base font-semibold text-slate-900">Weekly appointment volume</h2>
          <p className="mt-1 text-sm text-slate-500">Your cases versus the center average.</p>
          <div className="mt-4"><WeeklyVolumeChart data={dash.weeklyVolume} /></div>
        </section>
        <section className="rounded-2xl border border-[#E9EDF1] bg-white p-6 lg:col-span-1">
          <h2 className="text-base font-semibold text-slate-900">Case distribution</h2>
          <p className="mt-1 text-sm text-slate-500">Active cases by primary concern.</p>
          <div className="mt-4"><CaseDistributionChart segments={caseSegments} /></div>
        </section>
      </div>
    </div>
  </main>;
}
