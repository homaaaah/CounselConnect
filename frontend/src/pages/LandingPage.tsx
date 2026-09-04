import { Link } from "./LandingLink";
import { usePublicContent } from "../features/content";

/**
 * Public landing page (DFD Master System Flow entry).
 * Shows published announcements and office CMS content from content_items.
 */
export default function LandingPage({ onPreviewHome }: { onPreviewHome?: () => void }) {
  const { cmsBlocks, faqs, announcements, loading } = usePublicContent();

  const hero = cmsBlocks.find((b) => b.content_key === "landing_hero");

  return (
    <main className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">CounselConnect</h1>
          <p className="text-xs text-slate-500">
            University of Caloocan City — Guidance and Counseling Office
          </p>
        </div>
        <nav className="flex gap-3">
          <Link to="login">Sign in</Link>
          <Link to="register" variant="primary">
            Register
          </Link>
        </nav>
      </header>

      <section className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
        <h2 className="text-center text-3xl font-bold text-slate-800">
          {hero?.title ?? "Guidance and Counseling Services"}
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-center text-slate-600">
          {hero?.body ??
            "Schedule appointments, chat with your guidance counselor, access wellness resources, and get support when you need it — all in one place."}
        </p>

        <div className="mt-8 flex justify-center gap-4">
          <Link to="register" variant="primary" size="lg">
            Create your account
          </Link>
          <Link to="login" size="lg">
            Sign in
          </Link>
        </div>

        {onPreviewHome && (
          <p className="mt-4 text-center">
            <button
              onClick={onPreviewHome}
              className="text-xs text-slate-400 underline hover:text-slate-600"
            >
              Preview the signed-in homepage (real sign-in arrives with ADR-P01)
            </button>
          </p>
        )}
        <p className="mt-2 text-center">
          <a href="#review" className="text-xs text-slate-400 underline hover:text-slate-600">
            Counselor review console (dev)
          </a>
        </p>

        <div className="mt-12 grid gap-6 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Announcements
            </h3>
            {loading ? (
              <p className="mt-3 text-sm text-slate-400">Loading…</p>
            ) : announcements.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">No announcements yet.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {announcements.map((a) => (
                  <li key={a.content_id}>
                    <p className="text-sm font-medium text-slate-700">{a.title}</p>
                    <p className="mt-1 line-clamp-3 text-sm text-slate-500">{a.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Frequently Asked Questions
            </h3>
            {loading ? (
              <p className="mt-3 text-sm text-slate-400">Loading…</p>
            ) : faqs.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">No FAQs published yet.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {faqs.map((f) => (
                  <li key={f.content_id}>
                    <p className="text-sm font-medium text-slate-700">{f.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{f.body}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white px-6 py-4 text-center text-xs text-slate-400">
        CounselConnect — a centralized guidance-counseling platform.
      </footer>
    </main>
  );
}
