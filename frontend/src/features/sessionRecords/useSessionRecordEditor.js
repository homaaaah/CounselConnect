import { useEffect, useRef, useState } from "react";
import { EMPTY_RECORD, recordToForm, useSessionRecord } from "./useSessionRecord";

/**
 * Page-level record editor. Owning the form above the display tabs lets the
 * session header save the current assessment before completing the session.
 */
export function useSessionRecordEditor(appointmentId, enabled = true) {
  const recordApi = useSessionRecord(appointmentId, enabled);
  const [form, setForm] = useState(EMPTY_RECORD);
  const [dirty, setDirty] = useState(false);
  const previousStatus = useRef(null);

  // Identity/status changes (initial load, finalize, reopen, reload) replace
  // the form. A save that keeps the same DRAFT does not, so in-progress typing
  // is never overwritten by an autosave response (including the first save
  // that creates the record row). Finalize/reopen still win over local edits.
  useEffect(() => {
    const next = recordApi.record;
    if (!next) return;
    const statusChanged = previousStatus.current !== next.status;
    previousStatus.current = next.status;
    if (dirty && !statusChanged) return;
    setForm(recordToForm(next));
    setDirty(false);
  }, [recordApi.record?.record_id, recordApi.record?.status]);

  const update = (field, value) => {
    const next = { ...form, [field]: value };
    setForm(next);
    setDirty(true);
    if (recordApi.record?.can_edit) recordApi.queueSave(next);
  };

  const finalize = async () => {
    const saved = await recordApi.finalize();
    if (saved) {
      setForm(recordToForm(saved));
      setDirty(false);
    }
    return saved;
  };

  const reopen = async () => {
    const saved = await recordApi.reopen();
    if (saved) {
      setForm(recordToForm(saved));
      setDirty(false);
    }
    return saved;
  };

  const markDone = async onMarkDone => {
    // Save the current form first. An already-FINAL record needs no (and must
    // not receive) another PUT. After mount but before the sync effect runs,
    // fall back to the loaded record instead of writing EMPTY_RECORD.
    if (recordApi.record?.can_edit) {
      const saved = await recordApi.save(dirty ? form : recordToForm(recordApi.record));
      if (!saved) return null;
      setForm(recordToForm(saved));
      setDirty(false);
    }
    const result = await onMarkDone();
    await recordApi.reload();
    return result;
  };

  return { recordApi, form, update, finalize, reopen, markDone };
}
