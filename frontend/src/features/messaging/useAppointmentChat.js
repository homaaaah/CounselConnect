import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";
import { socketUrl } from "./useScheduledSessions";

const clientId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function useAppointmentChat(appointmentId) {
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [connection, setConnection] = useState("idle");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const socket = useRef(null);
  const reconnect = useRef(null);
  const latestSequence = useRef(0);

  const merge = useCallback((incoming) => {
    setMessages(previous => {
      const byId = new Map(previous.map(item => [item.message_id, item]));
      for (const item of incoming) byId.set(item.message_id, item);
      const ordered = [...byId.values()].sort((a, b) => a.sequence_number - b.sequence_number);
      latestSequence.current = ordered.at(-1)?.sequence_number || 0;
      return ordered;
    });
  }, []);

  const loadSession = useCallback(async (background = false) => {
    const data = await request(`/appointments/${appointmentId}/session`, background ? { headers: { "X-Background-Refresh": "1" } } : {});
    setSession(data);
    return data;
  }, [appointmentId]);

  const catchUp = useCallback(async (conversationId, after = 0) => {
    let cursor = after;
    for (;;) {
      const page = await request(`/conversations/${conversationId}/messages?after_sequence=${cursor}&limit=100`, { headers: { "X-Background-Refresh": "1" } });
      merge(page.items);
      if (page.items.length) cursor = page.items.at(-1).sequence_number;
      if (!page.has_more) break;
    }
  }, [merge]);

  const connect = useCallback((conversationId) => {
    const url = socketUrl(`/conversations/${conversationId}/ws`);
    if (typeof WebSocket === "undefined" || !url) return;
    socket.current?.close();
    setConnection("connecting");
    const ws = new WebSocket(url);
    socket.current = ws;
    ws.onopen = async () => {
      setConnection("connected");
      const last = latestSequence.current;
      try { await catchUp(conversationId, last); } catch { setError("Could not recover missed messages."); }
    };
    ws.onmessage = event => {
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.event === "message_created") merge([data.message]);
      if (["session_closed", "appointment_session_changed"].includes(data.event)) {
        void loadSession(true);
        if (data.event === "session_closed") setConnection("closed");
      }
    };
    ws.onclose = () => {
      if (socket.current !== ws) return;
      setConnection("reconnecting");
      reconnect.current = setTimeout(() => connect(conversationId), 1500);
    };
  }, [catchUp, loadSession, merge]);

  useEffect(() => {
    void loadSession().then(data => {
      if (data.conversation_id && data.capabilities.can_read_history) {
        void catchUp(data.conversation_id).then(() => {
          if (data.conversation_status === "OPEN") connect(data.conversation_id);
        });
      }
    }).catch(err => setError(err instanceof Error ? err.message : "Could not load the scheduled session."));
    const refresh = setInterval(() => void loadSession(true).catch(() => {}), 15000);
    return () => {
      clearInterval(refresh);
      clearTimeout(reconnect.current);
      const active = socket.current;
      socket.current = null;
      active?.close();
    };
  }, [appointmentId, catchUp, connect, loadSession]);

  const join = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const conversation = await request(`/appointments/${appointmentId}/session/join`, { method: "POST", body: "{}" });
      await loadSession();
      await catchUp(conversation.conversation_id);
      connect(conversation.conversation_id);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not join the session."); }
    finally { setBusy(false); }
  }, [appointmentId, catchUp, connect, loadSession]);

  const send = useCallback(async body => {
    if (!session?.conversation_id) return false;
    setBusy(true); setError("");
    try {
      const saved = await request(`/conversations/${session.conversation_id}/messages`, {
        method: "POST", body: JSON.stringify({ body, client_message_id: clientId() }),
      });
      merge([saved]); return true;
    } catch (err) { setError(err instanceof Error ? err.message : "Message failed to send."); return false; }
    finally { setBusy(false); }
  }, [session?.conversation_id, merge]);

  const outcome = useCallback(async action => {
    setBusy(true); setError("");
    try { await request(`/appointments/${appointmentId}/${action}`, { method: "POST", body: "{}" }); await loadSession(); return true; }
    catch (err) { setError(err instanceof Error ? err.message : "Could not close the appointment."); return false; }
    finally { setBusy(false); }
  }, [appointmentId, loadSession]);

  return { session, messages, connection, error, busy, join, send, outcome, loadSession };
}
