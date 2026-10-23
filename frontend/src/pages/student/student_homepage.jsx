import { useEffect, useState } from "react";
import { formatSchedule, useAppointments } from "../../features/appointments";
import { request } from "../../services/apiClient";
import BookingModal from "../../components/appointments/BookingModal.jsx";
import { useToast } from "../../components/feedback";

/**
 * One-shot recent-session fetch. Unlike useAppointments this does not load the
 * availability calendar/campuses/slots or poll — the homepage only shows the
 * latest records.
 */
function useRecentAppointments(enabled) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    request("/appointments?page=1&page_size=4")
      .then((data) => { if (!cancelled) setItems(data?.items ?? []); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [enabled]);
  return items;
}

/**
 * Student homepage component — redesigned to match Reference Image 1 (Bento layout):
 * Wide green greeting banner, Bento grid with Book a Schedule, Recent Sessions,
 * Notifications, and Emergency Support cards.
 */
function StudentBookingModal({ onClose, user }) {
  const state = useAppointments(user.role_code);
  return <BookingModal open={true} onClose={onClose} state={state} />;
}

export default function StudentHomePage({ user }) {
  const canBook = user?.role_code === "STUDENT" || user?.role_code === "COUNSELOR";
  const active = canBook && user?.account_status === "ACTIVE";
  const student = user?.role_code === "STUDENT";
  const [bookingOpen, setBookingOpen] = useState(false);
  const canOpenModal = student && active;
  const toast = useToast();

  // Recent sessions are only fetched for active students; the nav withholds
  // the Appointments link for other roles/statuses, so this stays consistent.
  const canViewRecords = student && active;
  const recentItems = useRecentAppointments(canViewRecords);

  return (
    <main className="min-h-screen bg-white px-4 py-8 text-slate-800 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        {/* Wide Green Greeting Banner (Reference Image 1) */}
        <section className="rounded-3xl bg-emerald-700 px-6 py-8 sm:px-10 sm:py-10 text-white shadow-md relative overflow-hidden">
          <div className="relative z-10 max-w-2xl">
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
              Hello{user?.first_name ? `, ${user.first_name}` : ""}!
            </h1>
            <p className="mt-2 text-emerald-100 text-sm sm:text-base leading-relaxed">
              Your gentle support space for guidance appointments, wellness resources, and counseling sessions.
            </p>
          </div>
          <div className="absolute right-6 top-1/2 -translate-y-1/2 opacity-10 hidden md:block pointer-events-none">
            <i className="fa-solid fa-heart-pulse text-9xl"></i>
          </div>
        </section>

        {/* Bento Grid (Reference Image 1) */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column (2 span on lg): Book a Schedule & Recent Sessions */}
          <div className="lg:col-span-2 space-y-6">
            {/* Book a Schedule Card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-6">
              <div className="space-y-3">
                <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 text-xl font-bold">
                  <i className="fa-solid fa-calendar-plus" aria-hidden="true"></i>
                </span>
                <h2 className="text-xl font-bold text-slate-900">Book a Schedule</h2>
                <p className="text-sm text-slate-600 max-w-md">
                  Reserve and manage your guidance sessions in real time — pick an open slot, confirm instantly, and get reminders.
                </p>
                {active ? (
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-full bg-emerald-700 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 transition-colors"
                    onClick={() => setBookingOpen(true)}
                  >
                    Start Booking <i className="fa-solid fa-arrow-right text-xs" aria-hidden="true"></i>
                  </button>
                ) : canBook ? (
                  <span className="inline-flex items-center gap-2 rounded-full bg-amber-100 px-6 py-3 text-sm font-semibold text-amber-800">
                    Verification {user?.account_status === "PENDING_VERIFICATION" ? "pending" : "needed"}
                  </span>
                ) : (
                  <a
                    href="#login"
                    className="inline-flex items-center gap-2 rounded-full bg-emerald-700 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-emerald-800 transition-colors"
                  >
                    Start Booking <i className="fa-solid fa-arrow-right text-xs" aria-hidden="true"></i>
                  </a>
                )}
              </div>
              <div className="shrink-0 hidden sm:flex h-36 w-36 items-center justify-center rounded-2xl bg-emerald-50/70 text-emerald-600 text-5xl">
                <i className="fa-regular fa-calendar-days"></i>
              </div>
            </div>

            {/* Recent Sessions / Appointments Card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-slate-900">Recent Sessions</h2>
                {canViewRecords && (
                  <a href="#appointments" className="text-sm font-semibold text-emerald-700 hover:underline">View all</a>
                )}
              </div>
              {recentItems.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-100 text-sm">
                    <thead>
                      <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                        <th className="pb-3">Counselor</th>
                        <th className="pb-3">Date & Time</th>
                        <th className="pb-3">Mode</th>
                        <th className="pb-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {recentItems.slice(0, 4).map(a => (
                        <tr key={a.appointment_id}>
                          <td className="py-3 font-medium text-slate-800">{a.counselor_name || "Assigned Counselor"}</td>
                          <td className="py-3 text-slate-600">{formatSchedule(a.starts_at)}</td>
                          <td className="py-3 text-slate-600">{a.appointment_mode}</td>
                          <td className="py-3">
                            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                              {a.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-8 text-center text-slate-500 text-sm">
                  No recent sessions recorded yet. Use "Book a Schedule" above to request one.
                </div>
              )}
            </div>
          </div>

          {/* Right Column (1 span on lg): Notifications & Emergency Support */}
          <div className="space-y-6">
            {/* Notifications Card */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-bold text-slate-900">Notifications</h2>
                <button type="button" onClick={() => toast.info("No new notifications.", { title: "Notifications" })} className="text-xs font-semibold text-emerald-700 hover:underline">View all</button>
              </div>
              <div className="space-y-3">
                <div className="rounded-xl bg-slate-50 p-3 text-xs space-y-1">
                  <div className="font-semibold text-slate-800">Welcome to CounselConnect</div>
                  <p className="text-slate-600">Your account is active. You can now schedule counseling appointments.</p>
                  <span className="text-[10px] text-slate-400">Just now</span>
                </div>
              </div>
            </div>

            {/* Emergency Support Card (Reference Image 1 - Soft Pink/Red) */}
            <div className="rounded-2xl border border-red-200 bg-red-50/70 p-6 shadow-sm space-y-4">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 text-red-600 font-bold">
                  <i className="fa-solid fa-phone" aria-hidden="true"></i>
                </span>
                <div>
                  <h2 className="text-base font-bold text-red-900">Need Immediate Help?</h2>
                  <p className="text-xs text-red-700">Emergency Support</p>
                </div>
              </div>
              <p className="text-sm text-red-800 leading-relaxed">
                If you or someone you know is facing a crisis, immediate professional assistance is available around the clock.
              </p>
              <button
                type="button"
                className="w-full rounded-full bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow hover:bg-red-700 transition-colors"
                onClick={() => {
                  toast.error("Emergency Support: Call 911 or the UCC Guidance Office hotline immediately for urgent crisis assistance.", { title: "Emergency Support", duration: 12000 });
                }}
              >
                Emergency
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Student booking modal — calendar, slot details, request */}
      {canOpenModal && bookingOpen && (
        <StudentBookingModal onClose={() => setBookingOpen(false)} user={user} />
      )}
    </main>
  );
}


