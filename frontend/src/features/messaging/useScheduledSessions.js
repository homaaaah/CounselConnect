import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE_URL, request } from "../../services/apiClient";

export function socketUrl(path) {
  if (typeof window === "undefined" || !window.location?.origin) return null;
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export function useScheduledSessions(user) {
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState("");
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    if (!user || user.account_status !== "ACTIVE" || !["STUDENT", "COUNSELOR"].includes(user.role_code)) return;
    try {
      const data = await request("/appointments/scheduled-sessions", { headers: { "X-Background-Refresh": "1" } });
      if (mounted.current) {
        setSessions(Array.isArray(data) ? data : []);
        setError("");
      }
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "Could not load scheduled sessions.");
    }
  }, [user?.user_id, user?.account_status, user?.role_code]);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const interval = setInterval(() => void refresh(), 60000);
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    let socket;
    const eventsUrl = socketUrl("/appointments/session-events");
    if (typeof WebSocket !== "undefined" && eventsUrl && user?.account_status === "ACTIVE") {
      socket = new WebSocket(eventsUrl);
      socket.onmessage = (message) => {
        let event;
        try { event = JSON.parse(message.data); } catch { return; }
        if (event.event === "appointment_reminder" && typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification("CounselConnect", { body: event.message });
        }
        void refresh();
      };
    }
    return () => {
      mounted.current = false;
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      socket?.close();
    };
  }, [refresh, user?.user_id, user?.account_status]);

  const selected = useMemo(() => {
    const active = sessions.find(item => item.capabilities?.can_send || item.capabilities?.can_join);
    return active || sessions.find(item => item.capabilities?.can_open_lobby) || sessions[0] || null;
  }, [sessions]);
  return { sessions, selected, error, refresh };
}
