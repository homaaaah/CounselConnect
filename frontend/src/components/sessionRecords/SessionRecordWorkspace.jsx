import { useEffect, useState } from "react";
import { formatSchedule } from "../../features/appointments";
import { useSessionRecordEditor } from "../../features/sessionRecords/useSessionRecordEditor";
import { useSessionDocuments } from "../../features/sessionRecords/useSessionDocuments";

const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm disabled:bg-slate-50 disabled:text-slate-500";
const labelClass = "block text-sm font-medium text-slate-700";
const primaryClass = "rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50";
const secondaryClass = "rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50";
const NO_MISSING_FIELDS = [];

const ASSESSMENT_FIELDS = [
  ["presenting_concern", "Presenting concern"],
  ["session_summary", "Session summary / observations"],
  ["intervention", "Intervention / action taken"],
  ["plan", "Plan / recommendation"],
];

function SavedState({ saving, savedAt }) {
  if (saving) return <span role="status" className="text-xs text-slate-500">Saving…</span>;
  if (savedAt) return <span role="status" className="text-xs text-slate-500">Saved {savedAt.toLocaleTimeString()}</span>;
  return null;
}

function NotesPanel({ record, form, update, saving, savedAt, locked }) {
  return <div>
    <label className={labelClass} htmlFor="session-notepad">Private notepad</label>
    <p className="mt-1 text-xs text-slate-500">Only you can read this. It is never shown to the Student.</p>
    <textarea id="session-notepad" className={fieldClass} rows={12} maxLength={20000}
      disabled={!record?.can_edit || locked} value={form.notepad}
      onChange={event => update("notepad", event.target.value)} />
    <div className="mt-2 text-right"><SavedState saving={saving} savedAt={savedAt} /></div>
  </div>;
}

function RecordPanel({
  record, form, update, saving, savedAt, onFinalize, onReopen,
  showFinalize, busy, missingFields,
}) {
  // Editing pauses while a save/completion request is in flight so no
  // debounced writer can race the finalize.
  const locked = !record?.can_edit || saving || busy;
  const missingLabels = ASSESSMENT_FIELDS
    .filter(([name]) => missingFields.includes(name))
    .map(([, label]) => label);
  const unknownFields = missingFields.filter(field => !ASSESSMENT_FIELDS.some(([name]) => name === field));
  return <div className="space-y-3">
    <p className="text-xs text-slate-500">Finalized records are read-only. This is not a diagnosis or medical advice.</p>
    {ASSESSMENT_FIELDS.map(([name, label]) => <label key={name} className={labelClass}>{label}
      <textarea className={fieldClass} rows={3} maxLength={20000} disabled={locked} value={form[name]}
        onChange={event => update(name, event.target.value)} />
    </label>)}
    <label className={labelClass}>Follow-up date (optional)
      <input type="date" className={fieldClass} disabled={locked} value={form.follow_up_on}
        onChange={event => update("follow_up_on", event.target.value)} />
    </label>
    <div className="flex flex-wrap items-center gap-3">
      {showFinalize && record?.can_finalize && <button type="button" className={primaryClass} disabled={saving} onClick={onFinalize}>Finalize record</button>}
      {record?.can_reopen && <button type="button" className={secondaryClass} disabled={saving || busy} onClick={onReopen}>Reopen for editing</button>}
      {record?.status === "FINAL" && <span className="text-xs font-semibold text-emerald-800">Finalized {formatSchedule(record.finalized_at)}</span>}
      <SavedState saving={saving} savedAt={savedAt} />
    </div>
    {missingFields.length > 0 && <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">
      Complete these assessment fields before marking the session done: {(missingLabels.length ? missingLabels : unknownFields).join(", ")}.
    </p>}
  </div>;
}

function AssessmentPanel({ record }) {
  if (!record) return <p className="text-sm text-slate-500">The Counselor has not finalized a session summary yet.</p>;
  return <div className="space-y-3">
    <p className="text-xs font-semibold text-emerald-800">Finalized {formatSchedule(record.finalized_at)}</p>
    {ASSESSMENT_FIELDS.map(([name, label]) => <div key={name}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-800">{record[name] || "—"}</p>
    </div>)}
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Follow-up date</p>
      <p className="mt-0.5 text-sm text-slate-800">{record.follow_up_on || "—"}</p>
    </div>
  </div>;
}

function FilesPanel({ documents, loading, busy, error, upload, remove, download, canUpload }) {
  return <div className="space-y-3">
    <div>
      <label className={labelClass} htmlFor="session-file">Add a PDF, JPEG, or PNG (max 10 MB)</label>
      <input id="session-file" className="mt-1 block w-full text-sm" type="file" accept=".pdf,.jpg,.jpeg,.png"
        disabled={busy || !canUpload} onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); event.target.value = ""; }} />
    </div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-2 text-sm text-red-700">{error}</p>}
    {loading && <p role="status" className="text-sm text-slate-500">Loading files…</p>}
    {!loading && documents.length === 0 && <p className="text-sm text-slate-500">No files yet.</p>}
    <ul className="space-y-2">
      {documents.map(doc => <li key={doc.document_id} className="rounded-lg border border-slate-200 p-3 text-sm">
        <p className="font-medium break-all">{doc.original_filename}</p>
        <p className="text-xs text-slate-500">{doc.uploader_name} · {Math.max(1, Math.round(doc.size_bytes / 1024))} KB · {formatSchedule(doc.created_at)}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" className={secondaryClass} onClick={() => void download(doc)}>Download</button>
          {doc.can_delete && <button type="button" className={secondaryClass} disabled={busy} onClick={() => void remove(doc.document_id)}>Delete</button>}
        </div>
      </li>)}
    </ul>
  </div>;
}

/**
 * Private session workspace. Counselors get Notes/Record/Files; Students see
 * only the finalized assessment and the shared files.
 *
 * The session page owns one editor instance (so its header can save the current
 * form before completing); other entry points let the workspace own it.
 */
export default function SessionRecordWorkspace(props) {
  if (props.editor) return <SessionRecordView {...props} />;
  return <StandaloneSessionRecordWorkspace {...props} />;
}

function StandaloneSessionRecordWorkspace({ appointment, ...props }) {
  const editor = useSessionRecordEditor(appointment.appointment_id, true);
  return <SessionRecordView {...props} appointment={appointment} editor={editor} />;
}

function SessionRecordView({
  user, appointment, variant = "page", editor, missingFields = NO_MISSING_FIELDS,
  actionBusy = false, scrollable = false,
}) {
  const counselor = user.role_code === "COUNSELOR";
  const filesEnabled = counselor || appointment.status === "COMPLETED";
  const recordApi = editor.recordApi;
  const { form, update, finalize, reopen } = editor;
  const files = useSessionDocuments(appointment.appointment_id, filesEnabled);
  const [tab, setTab] = useState(
    counselor
      ? (missingFields.length ? "record" : "notes")
      : (appointment.status === "COMPLETED" ? "assessment" : "files")
  );

  // A rejected header completion (RECORD_INCOMPLETE) must put the named fields
  // in front of the Counselor even if the workspace mounted on Notes.
  useEffect(() => {
    if (counselor && missingFields.length) setTab("record");
  }, [counselor, missingFields]);

  const tabs = counselor
    ? [["notes", "Notes"], ["record", "Record"], ["files", "Files"]]
    : [
        ...(appointment.status === "COMPLETED" ? [["assessment", "Assessment"]] : []),
        ["files", "Files"],
      ];
  const canUpload = ["CONFIRMED", "COMPLETED"].includes(appointment.status);

  return <section aria-label="Session workspace"
    className={scrollable ? "flex min-h-0 flex-1 flex-col gap-4" : "space-y-4"}>
    <div role="tablist" aria-label="Session workspace"
      className={"flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1" + (scrollable ? " shrink-0" : "")}>
      {tabs.map(([key, label]) => <button key={key} type="button" role="tab" aria-selected={tab === key}
        className={"flex-1 rounded-md px-3 py-1.5 text-sm font-semibold " + (tab === key ? "bg-white text-emerald-800 shadow-sm" : "text-slate-600 hover:text-slate-800")}
        onClick={() => setTab(key)}>{label}</button>)}
    </div>
    <div role="tabpanel" aria-label="Session workspace content"
      className={scrollable ? "min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1" : ""}
      tabIndex={scrollable ? 0 : undefined}>
      {recordApi.error && <div className="rounded-lg bg-red-50 p-2 text-sm text-red-700">
        <p role="alert">{recordApi.error}</p>
        {!recordApi.record && <button type="button" className={secondaryClass + " mt-2"} disabled={recordApi.loading} onClick={() => void recordApi.reload()}>Reload record</button>}
      </div>}
      {recordApi.loading && <p role="status" className="text-sm text-slate-500">Loading session record…</p>}

      {tab === "notes" && counselor && !recordApi.loading &&
        <NotesPanel record={recordApi.record} form={form} update={update} saving={recordApi.saving}
          savedAt={recordApi.savedAt} locked={actionBusy || recordApi.saving} />}
      {tab === "record" && counselor && !recordApi.loading &&
        <RecordPanel record={recordApi.record} form={form} update={update} saving={recordApi.saving}
          savedAt={recordApi.savedAt} onFinalize={finalize} onReopen={reopen}
          showFinalize={variant !== "rail"} busy={actionBusy} missingFields={missingFields} />}
      {tab === "assessment" && !counselor &&
        <AssessmentPanel record={recordApi.record} />}
      {tab === "files" && (filesEnabled
        ? <FilesPanel documents={files.documents} loading={files.loading} busy={files.busy} error={files.error}
          upload={files.upload} remove={files.remove} download={files.download} canUpload={canUpload} />
        : <p className="text-sm text-slate-500">Session files open after the Counselor marks the session completed.</p>)}
      {filesEnabled && !canUpload && tab === "files" && <p className="text-xs text-slate-500">Files can be added only for confirmed or completed sessions.</p>}
    </div>
    {variant === "rail" && <a href={`#session-record/${appointment.appointment_id}`} className="inline-block text-sm font-medium text-emerald-700">Open full page</a>}
  </section>;
}
