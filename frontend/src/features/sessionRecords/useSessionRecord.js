import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";

const AUTOSAVE_MS = 1500;

export const EMPTY_RECORD = {
  notepad: "",
  presenting_concern: "",
  session_summary: "",
  intervention: "",
  plan: "",
  follow_up_on: "",
};

export function recordToForm(record) {
  return record
    ? {
        notepad: record.notepad ?? "",
        presenting_concern: record.presenting_concern ?? "",
        session_summary: record.session_summary ?? "",
        intervention: record.intervention ?? "",
        plan: record.plan ?? "",
        follow_up_on: record.follow_up_on ?? "",
      }
    : EMPTY_RECORD;
}

/** Private counseling record: load, debounced draft autosave, finalize, reopen. */
export function useSessionRecord(appointmentId, enabled = true) {
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState("");
  const timer = useRef(null);
  const pending = useRef(null);
  const version = useRef(0);
  const path = `/appointments/${appointmentId}/record`;

  const load = useCallback(async () => {
    if (!enabled) return null;
    const current = ++version.current;
    setLoading(true);
    try {
      const data = await request(path);
      if (current !== version.current) return null;
      setRecord(data);
      setError("");
      return data;
    } catch (err) {
      if (current !== version.current) return null;
      // A Student sees 404 until the Counselor finalizes.
      setRecord(null);
      if (err.status !== 404) setError(err.message);
      return null;
    } finally {
      if (current === version.current) setLoading(false);
    }
  }, [path, enabled]);
  useEffect(() => { void load(); }, [load]);

  const save = useCallback(async values => {
    // An explicit save (including Mark as done) supersedes a pending debounce
    // so the same draft cannot be written again after the record is finalized.
    clearTimeout(timer.current);
    pending.current = null;
    const current = ++version.current;
    setSaving(true);
    try {
      const saved = await request(path, {
        method: "PUT",
        body: JSON.stringify({
          notepad: values.notepad ?? null,
          presenting_concern: values.presenting_concern ?? null,
          session_summary: values.session_summary ?? null,
          intervention: values.intervention ?? null,
          plan: values.plan ?? null,
          follow_up_on: values.follow_up_on || null,
        }),
      });
      if (current !== version.current) return saved;
      setRecord(saved);
      setSavedAt(new Date());
      setError("");
      return saved;
    } catch (err) {
      if (current === version.current) setError(err.message);
      return null;
    } finally {
      if (current === version.current) setSaving(false);
    }
  }, [path]);

  const queueSave = useCallback(values => {
    pending.current = values;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      const next = pending.current;
      pending.current = null;
      if (next) void save(next);
    }, AUTOSAVE_MS);
  }, [save]);

  const flush = useCallback(async () => {
    clearTimeout(timer.current);
    const next = pending.current;
    pending.current = null;
    return next ? save(next) : null;
  }, [save]);

  // Flush a pending debounce when the rail tab unmounts; losing a note is worse
  // than a request whose result is discarded.
  useEffect(() => () => {
    clearTimeout(timer.current);
    const next = pending.current;
    pending.current = null;
    if (next) void save(next);
  }, [save]);

  const action = useCallback(async suffix => {
    const current = ++version.current;
    setSaving(true);
    try {
      const saved = await request(`${path}/${suffix}`, { method: "POST" });
      if (current !== version.current) return saved;
      setRecord(saved);
      setSavedAt(new Date());
      setError("");
      return saved;
    } catch (err) {
      if (current === version.current) setError(err.message);
      return null;
    } finally {
      if (current === version.current) setSaving(false);
    }
  }, [path]);

  const finalize = useCallback(async () => { await flush(); return action("finalize"); }, [action, flush]);
  const reopen = useCallback(() => action("reopen"), [action]);

  return { record, loading, saving, savedAt, error, save, queueSave, flush, finalize, reopen, reload: load };
}
