import { useState } from "react";
import { useRegistration, EMPTY_FORM, RegistrationForm } from "../features/accounts";

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none";

/** Student registration (DFD 1.1 + 1.2): details + COR PDF, ONE submit. */
export default function RegisterPage() {
  const { campuses, programs, register, submitting } = useRegistration();
  const [form, setForm] = useState<RegistrationForm>(EMPTY_FORM);
  const [corFile, setCorFile] = useState<File | null>(null);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  function set<K extends keyof RegistrationForm>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResult(await register(form, corFile));
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-10">
      <div className="w-full max-w-2xl rounded-lg border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-800">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">
          Register with your details and attach your current registration form (COR) —
          your proof of enrollment at the University of Caloocan City. Everything is
          submitted together for Guidance Counselor approval.
        </p>

        <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleSubmit} encType="multipart/form-data">
          <div>
            <label className="text-sm font-medium text-slate-700">First name</label>
            <input required className={inputClass} value={form.first_name}
              onChange={(e) => set("first_name", e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Last name</label>
            <input required className={inputClass} value={form.last_name}
              onChange={(e) => set("last_name", e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Middle name (optional)</label>
            <input className={inputClass} value={form.middle_name}
              onChange={(e) => set("middle_name", e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Student number</label>
            <input required className={inputClass} placeholder="e.g. 2026-00001"
              value={form.student_number}
              onChange={(e) => set("student_number", e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className="text-sm font-medium text-slate-700">Email</label>
            <input required type="email" className={inputClass} value={form.email}
              onChange={(e) => set("email", e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className="text-sm font-medium text-slate-700">Password (8+ characters)</label>
            <input required type="password" minLength={8} className={inputClass}
              value={form.password} onChange={(e) => set("password", e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Campus</label>
            <select required className={inputClass} value={form.campus_id}
              onChange={(e) => set("campus_id", e.target.value)}>
              <option value="" disabled>Select campus</option>
              {campuses.map((c) => (
                <option key={c.campus_id} value={c.campus_id}>{c.campus_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Program</label>
            <select required className={inputClass} value={form.program_id}
              onChange={(e) => set("program_id", e.target.value)}>
              <option value="" disabled>Select program</option>
              {programs.map((p) => (
                <option key={p.program_id} value={p.program_id}>{p.program_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Year level</label>
            <select required className={inputClass} value={form.year_level}
              onChange={(e) => set("year_level", e.target.value)}>
              {[1, 2, 3, 4, 5, 6].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Section</label>
            <input required maxLength={50} className={inputClass} value={form.section}
              onChange={(e) => set("section", e.target.value)} />
          </div>

          <div className="md:col-span-2 rounded-md border border-slate-200 bg-slate-50 p-4">
            <label className="text-sm font-medium text-slate-700">
              Registration form (COR) — required PDF
            </label>
            <p className="mt-1 text-xs text-slate-500">
              Your Certificate of Registration is the required proof of current enrollment.
              PDF only, max 10 MB. Stored privately and deleted after the decision.
            </p>
            <input
              required
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setCorFile(e.target.files?.[0] ?? null)}
              className="mt-2 w-full text-sm"
            />
            {corFile && (
              <p className="mt-2 text-xs text-emerald-600">
                Attached: {corFile.name} ({(corFile.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          <div className="md:col-span-2">
            <button type="submit" disabled={submitting}
              className="w-full rounded-md bg-emerald-600 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50">
              {submitting ? "Submitting…" : "Submit registration for approval"}
            </button>
          </div>
        </form>

        {result && (
          <p className={`mt-4 rounded-md p-3 text-sm ${
            result.success ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"
          }`}>
            {result.message}
          </p>
        )}

        <p className="mt-6 text-center text-xs text-slate-400">
          <a href="#landing" className="hover:underline">Back to landing page</a>
        </p>
      </div>
    </main>
  );
}
