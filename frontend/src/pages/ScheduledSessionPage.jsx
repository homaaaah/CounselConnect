import { useEffect, useRef, useState } from "react";
import { formatSchedule } from "../features/appointments";
import { useAppointmentChat } from "../features/messaging/useAppointmentChat";
import { useSessionRecordEditor } from "../features/sessionRecords/useSessionRecordEditor";
import AppointmentCallPanel from "../components/calls/AppointmentCallPanel";
import ConcernSummary from "../components/appointments/ConcernSummary.jsx";
import SessionRecordWorkspace from "../components/sessionRecords/SessionRecordWorkspace";
import { request } from "../services/apiClient";

function SessionChat({ chat, user, body, setBody }) {
  if (!chat.session.conversation_id) return null;
  return <div className="flex min-h-0 flex-1 flex-col">
    <p role="status" className="text-xs text-slate-500">Connection: {chat.connection}</p>
    <ol className="mt-4 min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain rounded-lg bg-slate-50 p-4" aria-label="Session messages" tabIndex={0}>
      {chat.messages.map(message => <li key={message.message_id} className={message.sender_user_id === user.user_id ? "ml-auto max-w-[80%] rounded-lg bg-emerald-700 p-3 text-sm text-white" : "max-w-[80%] rounded-lg bg-white p-3 text-sm shadow-sm"}>{message.body}</li>)}
      {!chat.messages.length && <li className="text-sm text-slate-500">No messages yet.</li>}
    </ol>
    {chat.session.capabilities.can_send && <form className="mt-4 flex shrink-0 gap-2" onSubmit={async event => { event.preventDefault(); const text = body; if (await chat.send(text)) setBody(""); }}>
      <label className="sr-only" htmlFor="chat-message">Message</label>
      <textarea id="chat-message" className="min-h-20 flex-1 rounded-lg border border-slate-300 p-3" maxLength={4000} required value={body} onChange={event => setBody(event.target.value)} />
      <button className="self-end rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white" disabled={chat.busy || !body.trim()}>Send</button>
    </form>}
  </div>;
}

function SessionDetails({ appointment, session }) {
  const rows = [
    ["Student", appointment?.student_name ?? "—"],
    ["Campus", appointment?.campus_name ?? "—"],
    ["Mode", (appointment?.appointment_mode ?? session.appointment_mode) === "FACE_TO_FACE" ? "Face to face" : "Online"],
    ["Schedule", `${formatSchedule(session.starts_at)} – ${formatSchedule(session.ends_at)}`],
    ["Status", session.status.replaceAll("_", " ")],
  ];
  return <div className="space-y-4">
    <dl className="space-y-3 text-sm">
      {rows.map(([label, value]) => <div key={label}>
        <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
        <dd className="mt-0.5 text-slate-800">{value}</dd>
      </div>)}
    </dl>
    <ConcernSummary categories={appointment?.concern_categories} details={appointment?.concern_details} />
  </div>;
}

export default function ScheduledSessionPage({ user, appointmentId }) {
  const chat = useAppointmentChat(appointmentId);
  const isCounselor = user.role_code === "COUNSELOR";
  const editor = useSessionRecordEditor(appointmentId, isCounselor);
  const [appointment, setAppointment] = useState(null);
  const [body, setBody] = useState("");
  const [tab, setTab] = useState("chat");
  const [joinFailed, setJoinFailed] = useState(false);
  const autoJoinAttempted = useRef(false);
  const openRefreshAttempted = useRef(false);
  const [, tick] = useState(0);
  useEffect(() => { const timer = setInterval(() => tick(value => value + 1), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    let cancelled = false;
    request(`/appointments/${appointmentId}`)
      .then(data => { if (!cancelled) setAppointment(data); })
      .catch(() => { /* Names fall back to role labels; the call still works. */ });
    return () => { cancelled = true; };
  }, [appointmentId]);
  useEffect(() => {
    autoJoinAttempted.current = false;
    openRefreshAttempted.current = false;
    setJoinFailed(false);
  }, [appointmentId]);
  const chatOpen = Boolean(chat.session)
    && Date.now() >= new Date(chat.session.messaging_opens_at).getTime();
  // The cached lobby session may still say can_join=false at the boundary; a
  // single background refresh lets the join be evaluated post-start without
  // waiting for the 15-second interval (and without renewing idle activity).
  useEffect(() => {
    if (!chat.session) return;
    const joined = isCounselor ? chat.session.counselor_joined_at : chat.session.student_joined_at;
    if (!chatOpen || joined || chat.session.capabilities.can_join || chat.busy || openRefreshAttempted.current) return;
    openRefreshAttempted.current = true;
    void chat.loadSession(true).catch(() => {});
  }, [chat.session, chatOpen, chat.busy, isCounselor, chat.loadSession]);
  // Join once when the page is already open at/after the start. The ref stops
  // a failed attempt from retrying on every tick; the role's join timestamp is
  // the already-joined signal because can_join stays true after joining.
  useEffect(() => {
    if (!chat.session) return;
    const joined = isCounselor ? chat.session.counselor_joined_at : chat.session.student_joined_at;
    if (!chatOpen || !chat.session.capabilities.can_join || joined || chat.busy || autoJoinAttempted.current) return;
    autoJoinAttempted.current = true;
    setJoinFailed(false);
    void chat.join({ background: true }).then(ok => { if (!ok) setJoinFailed(true); });
  }, [chat.session, chatOpen, chat.busy, isCounselor, chat.join]);
  if (!chat.session) return <main className="p-6"><p role="status">Loading scheduled session…</p>{chat.error && <p role="alert">{chat.error}</p>}</main>;
  const session = chat.session;
  const workspaceAppointment = {
    ...(appointment || {}), appointment_id: appointmentId, status: session.status,
  };
  const selfName = isCounselor ? appointment?.counselor_name : appointment?.student_name;
  const sessionStarted = Date.now() >= new Date(session.starts_at).getTime();
  const beforeStart = Date.now() < new Date(session.messaging_opens_at).getTime();
  const participantJoined = isCounselor
    ? session.counselor_joined_at
    : session.student_joined_at;

  const retryJoin = async () => {
    setJoinFailed(false);
    const ok = await chat.join();
    if (!ok) setJoinFailed(true);
  };
  const markSessionDone = async () => {
    const result = await editor.markDone(chat.markDone);
    if (!result) setTab("record");
  };

  return <main className="min-h-screen bg-slate-50 px-4 py-6 text-slate-800 lg:h-full lg:min-h-0 lg:overflow-hidden">
    <div className="mx-auto max-w-7xl lg:flex lg:h-full lg:flex-col">
      <a href="#appointments" className="shrink-0 text-sm font-medium text-emerald-700">← Back to appointments</a>
      <div className="mt-3 grid gap-6 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 lg:min-h-0 lg:overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-bold">Live session</h1>
              <p className="mt-1 text-sm text-slate-500">{formatSchedule(session.starts_at)} to {formatSchedule(session.ends_at)}</p>
            </div>
            {isCounselor && sessionStarted && session.status === "CONFIRMED" &&
              <div className="flex flex-wrap gap-2">
                {editor.recordApi.record &&
                  <button className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={chat.busy || editor.recordApi.loading || editor.recordApi.saving}
                    onClick={() => void markSessionDone()}>Mark as done</button>}
                <button className="rounded-lg border border-slate-300 px-4 py-2 text-sm" disabled={chat.busy} onClick={() => void chat.outcome("no-show")}>Mark no-show</button>
              </div>}
          </div>
          <AppointmentCallPanel
            appointmentId={appointmentId}
            canCall={session.capabilities.can_call === true}
            startsAt={session.starts_at}
            safetyDeadlineAt={session.safety_deadline_at}
            serverTime={session.server_time}
            appointmentMode={session.appointment_mode}
            status={session.status}
            now={Date.now()}
            selfName={selfName}
          />
          {chat.error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-700">{chat.error}</p>}
          {beforeStart && <section className="mt-6 rounded-lg bg-emerald-50 p-5">
            <h2 className="font-semibold">Session lobby</h2>
            <p className="mt-1 text-sm">You are ready. Messaging opens at the scheduled start.</p>
          </section>}
          {chatOpen && !participantJoined && chat.busy &&
            <p role="status" className="mt-6 rounded-lg bg-emerald-50 p-4 text-sm">Joining the session…</p>}
          {chatOpen && !participantJoined && !chat.busy && joinFailed &&
            <div className="mt-6 rounded-lg bg-red-50 p-4">
              <p className="text-sm text-red-700">The session could not be joined automatically.</p>
              <button className="mt-3 rounded-lg bg-emerald-700 px-5 py-2.5 font-semibold text-white" onClick={() => void retryJoin()}>Retry joining</button>
            </div>}
          {session.conversation_status === "CLOSED" && <p className="mt-4 rounded-lg bg-slate-100 p-3 text-sm">This conversation is closed{session.closure_reason === "TIMEOUT" ? ". The Counselor still needs to record the session outcome." : "."}</p>}
        </div>
        <aside aria-label="Session panel" className="flex min-h-0 max-h-[75dvh] flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:max-h-full">
          <div role="tablist" aria-label="Session panel" className="flex shrink-0 flex-wrap gap-1 rounded-lg bg-slate-100 p-1">
            {(isCounselor
              ? [["chat", "Session chat"], ["record", "Session record"], ["details", "Details"]]
              : [["chat", "Session chat"], ["details", "Details"]]).map(([key, label]) => (
              <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                className={"flex-1 rounded-md px-3 py-1.5 text-sm font-semibold " + (tab === key ? "bg-white text-emerald-800 shadow-sm" : "text-slate-600 hover:text-slate-800")}>
                {label}
              </button>
            ))}
          </div>
          <div role="tabpanel" aria-label={tab === "chat" ? "Session chat" : tab === "record" ? "Session record" : "Details"}
            className={tab === "chat"
              ? "mt-4 flex min-h-0 flex-1 flex-col overflow-hidden"
              : "mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1"}
            tabIndex={tab === "chat" ? undefined : 0}>
            {tab === "chat" && <SessionChat chat={chat} user={user} body={body} setBody={setBody} />}
            {isCounselor && tab === "record" && <SessionRecordWorkspace user={user} variant="rail"
              appointment={workspaceAppointment} editor={editor}
              missingFields={chat.missingFields} actionBusy={chat.busy} />}
            {tab === "details" && <SessionDetails appointment={appointment} session={session} />}
          </div>
          {!isCounselor && (session.status === "COMPLETED"
            ? <a href={`#session-record/${appointmentId}`} className="mt-4 inline-block shrink-0 text-sm font-medium text-emerald-700">Session files &amp; summary</a>
            : <span aria-disabled="true" title="Available after the session is completed" className="mt-4 inline-block shrink-0 cursor-not-allowed text-sm font-medium text-slate-400">Session files &amp; summary</span>)}
        </aside>
      </div>
    </div>
  </main>;
}
