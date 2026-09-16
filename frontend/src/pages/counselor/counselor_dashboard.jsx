import { useAppointmentCount } from "../../features/appointments";

/**
 * Counselor dashboard component extracted from HomePage.jsx.
 */

function StatCard({ label, value, icon, loading, placeholder, href }) {
  const body = <div className="dashboard-stat-card flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-6">
    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-counseling-bg-tint text-xl text-counseling-active-focus">
      <i className={"fa-solid " + icon} aria-hidden="true"></i>
    </span>
    <div className="min-w-0">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-900">
        {loading ? "…" : value ?? placeholder}
      </p>
    </div>
  </div>;
  return href ? <a href={href} className="block">{body}</a> : body;
}

export default function CounselorDashboard({ user }) {
  const appointments = useAppointmentCount();
  return <main className="home-page">
    <section className="dashboard-hero px-4 pt-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-2xl font-bold text-slate-900">Welcome back, {user.first_name}.</h1>
        <p className="mt-1 text-sm text-slate-500">Here's an overview of your Guidance Office today. Philippine time (Asia/Manila).</p>

        {/* Stat cards.
            TODO(team): "Total users" has no backend endpoint yet — swap the
            placeholder for real data when the user-count API ships. */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <StatCard label="Total users" value={null} placeholder="—"
            icon="fa-users" loading={false} />
          <StatCard label="Appointments" value={appointments.total}
            icon="fa-calendar" loading={appointments.loading}
            href={appointments.error ? null : "#appointments"} />
        </div>
        {appointments.error && <p role="alert" className="mt-3 text-sm text-red-700">{appointments.error}</p>}

        <div className="mt-6 flex flex-wrap gap-3">
          <a href="#appointments" className="btn-action-schedule">
            <i className="fa-solid fa-calendar"></i> View appointments
          </a>
          <a href="#review" className="btn-action-emergency">
            <i className="fa-solid fa-users"></i> Verify students
          </a>
        </div>
      </div>
    </section>
  </main>;
}
