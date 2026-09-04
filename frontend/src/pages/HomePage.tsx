import { usePublicContent } from "../features/content";

/**
 * Homepage after sign-in (DFD Master System Flow "Student services").
 * Until ADR-P01, reached via the demo link on the landing page; shows the
 * student service modules and emergency contacts.
 */
export default function HomePage() {
  const { announcements, contacts } = usePublicContent();

  const services = [
    { title: "Appointments", desc: "Book and manage guidance appointments." },
    { title: "Live Chat", desc: "Message your guidance counselor in real time." },
    { title: "SOS", desc: "Confidential triage and immediate support." },
    { title: "Wellness Library", desc: "Browse reviewed wellness resources." },
    { title: "Virtual Assistant", desc: "Get answers about services and FAQs." },
  ];

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold text-slate-800">CounselConnect</h1>
        <span className="text-xs text-slate-400">
          Preview — sign-in arrives with ADR-P01
        </span>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <h2 className="text-2xl font-bold text-slate-800">Student services</h2>
        <p className="mt-2 text-sm text-slate-500">
          Access to these services requires an active verified enrollment
          (DFD role gate: pending or expired accounts get verification only).
        </p>

        <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {services.map((s) => (
            <div key={s.title}
              className="rounded-lg border border-slate-200 bg-white p-5 opacity-90">
              <h3 className="font-medium text-slate-800">{s.title}</h3>
              <p className="mt-1 text-sm text-slate-500">{s.desc}</p>
              <p className="mt-3 text-xs font-medium text-amber-600">
                Available after COR verification
              </p>
            </div>
          ))}
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Announcements
            </h3>
            {announcements.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">No announcements yet.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {announcements.map((a) => (
                  <li key={a.content_id}>
                    <p className="text-sm font-medium text-slate-700">{a.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{a.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-red-200 bg-red-50 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-red-600">
              Emergency contacts
            </h3>
            {contacts.length === 0 ? (
              <p className="mt-3 text-sm text-red-400">
                No contacts configured yet.
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {contacts.map((c) => (
                  <li key={c.contact_id}>
                    <p className="text-sm font-medium text-red-800">{c.name}</p>
                    <p className="text-sm text-red-600">{c.contact_number}</p>
                    {c.description && (
                      <p className="text-xs text-red-500">{c.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
