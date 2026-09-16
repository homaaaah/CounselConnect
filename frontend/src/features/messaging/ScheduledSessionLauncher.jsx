import { useEffect, useState } from "react";
import { formatSchedule } from "../appointments";
import { useScheduledSessions } from "./useScheduledSessions";

const remaining = (target, now) => {
  const seconds = Math.max(0, Math.ceil((new Date(target).getTime() - now) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
};

export default function ScheduledSessionLauncher({ user }) {
  const { sessions } = useScheduledSessions(user);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const current = sessions.find(item => now < new Date(item.safety_deadline_at).getTime())
    || (user.role_code === "COUNSELOR" ? sessions.find(item => item.closure_reason === "TIMEOUT") : null);
  if (!current) return null;
  const selected = current;
  const lobbyOpen = now >= new Date(selected.lobby_opens_at).getTime()
    && now < new Date(selected.safety_deadline_at).getTime();
  const sessionOpen = now >= new Date(selected.messaging_opens_at).getTime()
    && now < new Date(selected.safety_deadline_at).getTime();
  const enabled = lobbyOpen || sessionOpen;
  const label = sessionOpen
    ? "Open scheduled session"
    : lobbyOpen
      ? "Open session lobby"
      : `Session opens in ${remaining(selected.lobby_opens_at, now)}`;
  return <div className="fixed bottom-6 right-5 z-30 max-w-xs rounded-xl border border-emerald-200 bg-white p-3 shadow-lg">
    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Scheduled online session</p>
    <p className="mt-1 text-sm text-slate-600">{formatSchedule(selected.starts_at)}</p>
    <button type="button" disabled={!enabled}
      className="mt-2 w-full rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
      onClick={() => { window.location.hash = `session/${selected.appointment_id}`; }}>
      <i className="fa-solid fa-comments mr-2" aria-hidden="true"></i>{label}
    </button>
  </div>;
}
