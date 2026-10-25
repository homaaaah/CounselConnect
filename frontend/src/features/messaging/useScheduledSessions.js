import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { request } from "../../services/apiClient";
import { socketUrl } from "../../services/realtime";

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
        if (["appointment_requested", "appointment_session_changed", "appointment_confirmed", "session_closed"].includes(event.event)) {
          window.dispatchEvent(new CustomEvent("appointment-updated", { detail: event }));
          if (event.event === "appointment_requested" && user?.role_code === "COUNSELOR") {
            window.dispatchEvent(new CustomEvent("counselconnect-toast", {
              detail: { message: "A new appointment request is ready for review." },
            }));
          }
          if (event.event === "appointment_confirmed" && user?.role_code === "STUDENT") {
            window.dispatchEvent(new CustomEvent("counselconnect-toast", {
              detail: { message: "Your appointment has been confirmed." },
            }));
          }
        }
        void refresh();
      };
    }
    return () => {
      mounted.current = false;
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
      // Closing a socket that is still CONNECTING logs "WebSocket is closed
      // before the connection is established" (seen under StrictMode's
      // setup->cleanup->setup). Defer the close until it opens instead.
      if (socket) {
        if (socket.readyState === WebSocket.CONNECTING && typeof socket.addEventListener === "function") {
          socket.addEventListener("open", () => socket.close(), { once: true });
        } else {
          socket.close();
        }
      }
    };
  }, [refresh, user?.user_id, user?.account_status]);

  const selected = useMemo(() => {
    const active = sessions.find(item => item.capabilities?.can_send || item.capabilities?.can_join);
    return active || sessions.find(item => item.capabilities?.can_open_lobby) || sessions[0] || null;
  }, [sessions]);
  return { sessions, selected, error, refresh };
}
