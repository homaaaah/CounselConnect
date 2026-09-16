import { useEffect, useState } from "react";
import { formatSchedule } from "../features/appointments";
import { useAppointmentChat } from "../features/messaging/useAppointmentChat";

export default function ScheduledSessionPage({ user, appointmentId }) {
  const chat = useAppointmentChat(appointmentId);
  const [body, setBody] = useState("");
  const [, tick] = useState(0);
  useEffect(() => { const timer = setInterval(() => tick(value => value + 1), 1000); return () => clearInterval(timer); }, []);
  if (!chat.session) return <main className="p-6"><p role="status">Loading scheduled session…</p>{chat.error && <p role="alert">{chat.error}</p>}</main>;
  const session = chat.session;
  const beforeStart = Date.now() < new Date(session.messaging_opens_at).getTime();
  const participantJoined = user.role_code === "COUNSELOR"
    ? session.counselor_joined_at
    : session.student_joined_at;
  return <main className="min-h-screen bg-slate-50 px-4 py-8 text-slate-800">
    <div className="mx-auto max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <a href="#appointments" className="text-sm font-medium text-emerald-700">← Back to appointments</a>
      <h1 className="mt-3 text-2xl font-bold">Scheduled counseling session</h1>
      <p className="mt-1 text-sm text-slate-500">{formatSchedule(session.starts_at)} to {formatSchedule(session.ends_at)}</p>
      {chat.error && <p role="alert" className="mt-4 rounded-lg bg-red-50 p-3 text-red-700">{chat.error}</p>}
      {beforeStart && <section className="mt-6 rounded-lg bg-emerald-50 p-5">
        <h2 className="font-semibold">Session lobby</h2>
        <p className="mt-1 text-sm">You are ready. Messaging opens at the scheduled start.</p>
      </section>}
      {!beforeStart && !participantJoined && session.capabilities.can_join &&
        <button className="mt-6 rounded-lg bg-emerald-700 px-5 py-2.5 font-semibold text-white" disabled={chat.busy} onClick={() => void chat.join()}>Join scheduled session</button>}
      {session.conversation_id && <>
        <p role="status" className="mt-4 text-xs text-slate-500">Connection: {chat.connection}</p>
        <ol className="mt-4 max-h-[28rem] space-y-3 overflow-y-auto rounded-lg bg-slate-50 p-4" aria-label="Session messages">
          {chat.messages.map(message => <li key={message.message_id} className={message.sender_user_id === user.user_id ? "ml-auto max-w-[80%] rounded-lg bg-emerald-700 p-3 text-sm text-white" : "max-w-[80%] rounded-lg bg-white p-3 text-sm shadow-sm"}>{message.body}</li>)}
          {!chat.messages.length && <li className="text-sm text-slate-500">No messages yet.</li>}
        </ol>
        {session.capabilities.can_send && <form className="mt-4 flex gap-2" onSubmit={async event => { event.preventDefault(); const text = body; if (await chat.send(text)) setBody(""); }}>
          <label className="sr-only" htmlFor="chat-message">Message</label>
          <textarea id="chat-message" className="min-h-20 flex-1 rounded-lg border border-slate-300 p-3" maxLength={4000} required value={body} onChange={event => setBody(event.target.value)} />
          <button className="self-end rounded-lg bg-emerald-700 px-4 py-2 font-semibold text-white" disabled={chat.busy || !body.trim()}>Send</button>
        </form>}
      </>}
      {session.conversation_status === "CLOSED" && <p className="mt-4 rounded-lg bg-slate-100 p-3 text-sm">This conversation is closed{session.closure_reason === "TIMEOUT" ? ". The Counselor still needs to record the session outcome." : "."}</p>}
      {user.role_code === "COUNSELOR" && Date.now() >= new Date(session.starts_at).getTime() && session.status === "CONFIRMED" && <div className="mt-6 flex flex-wrap gap-2 border-t pt-4">
        <button className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white" disabled={chat.busy} onClick={() => void chat.outcome("complete")}>Mark completed</button>
        <button className="rounded-lg border border-slate-300 px-4 py-2 text-sm" disabled={chat.busy} onClick={() => void chat.outcome("no-show")}>Mark no-show</button>
      </div>}
    </div>
  </main>;
}
