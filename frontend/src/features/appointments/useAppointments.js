import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";

export const formatSchedule = (value) => new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila", dateStyle: "medium", timeStyle: "short",
}).format(new Date(value));
export const manilaInputToUTC = (value) => new Date(value + ":00+08:00").toISOString();
/** Current Philippine calendar date (YYYY-MM-DD), independent of the browser timezone. */
export const manilaToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
/** Manila-local "YYYY-MM-DDTHH:MM" string for datetime-local input bounds. */
export const manilaLocalInput = (date) => {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).formatToParts(date);
  const get = (type) => parts.find(part => part.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
};
/** True when the slot's scheduled start (UTC ISO) has already passed. */
export const slotIsPast = (slot, now = new Date()) => new Date(slot.starts_at).getTime() <= now.getTime();

/**
 * initialStatus seeds the records filter (e.g. "CONFIRMED" default on the
 * appointments page); empty string loads all statuses.
 */
export function useAppointments(role = "", initialStatus = "") {
  const [campuses, setCampuses] = useState([]);
  const [slots, setSlots] = useState({ items: [], page: 1, page_size: 20, total: 0 });
  const [appointments, setAppointments] = useState({ items: [], page: 1, page_size: 20, total: 0 });
  const [calendar, setCalendar] = useState(null);
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [availabilityBlocks, setAvailabilityBlocks] = useState([]);
  const [campusId, setCampusId] = useState("");
  const [mode, setMode] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState(initialStatus);
  const [slotPage, setSlotPage] = useState(1);
  const [appointmentPage, setAppointmentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  const mounted = useRef(true);
  const mutating = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);

  const refresh = useCallback(async (background = false) => {
    const current = ++sequence.current;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ page: String(slotPage), page_size: "20" });
    if (campusId) params.set("campus_id", campusId);
    if (mode) params.set("appointment_mode", mode);
    const todayManila = manilaToday();
    const effectiveDate = date && date >= todayManila ? date : "";
    if (effectiveDate) {
      params.set("starts_after", new Date(effectiveDate + "T00:00:00+08:00").toISOString());
      params.set("ends_before", new Date(new Date(effectiveDate + "T00:00:00+08:00").getTime() + 86400000).toISOString());
    }
    const appParams = new URLSearchParams({ page: String(appointmentPage), page_size: "20" });
    if (status) appParams.set("status", status);
    try {
      const today = new Date();
      const manilaDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(today);
      const end = new Date(today); end.setDate(end.getDate() + 30);
      const endDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(end);
      const calendarParams = new URLSearchParams({ start_date: manilaDate, end_date: endDate });
      const headers = background ? { "X-Background-Refresh": "1" } : undefined;
      const calendarData = await request("/calendar?" + calendarParams, { headers });
      const isCounselor = role === "COUNSELOR";
      const [campusData, slotData, appointmentData, scheduleData, blockData] = await Promise.all([
        request("/accounts/campuses", { headers }),
        request("/availability-slots?" + params, { headers }),
        request("/appointments?" + appParams, { headers }),
        isCounselor ? request("/weekly-schedules", { headers }) : Promise.resolve([]),
        isCounselor ? request("/availability-blocks", { headers }) : Promise.resolve([]),
      ]);
      if (current !== sequence.current || !mounted.current) return;
      setCampuses(campusData.items);
      // A slot becomes unbookable the moment its start passes; the backend
      // already excludes past slots, this covers the gap until refresh.
      const stillFuture = slotData.items.filter(slot => new Date(slot.starts_at).getTime() > Date.now());
      setSlots({ ...slotData, items: stillFuture, total: slotData.total });
      setAppointments(appointmentData); setCalendar(calendarData);
      setWeeklySchedules(scheduleData); setAvailabilityBlocks(blockData);
    } catch (err) {
      if (current === sequence.current && mounted.current) {
        setSlots({ items: [], page: slotPage, page_size: 20, total: 0 });
        setAppointments({ items: [], page: appointmentPage, page_size: 20, total: 0 });
        setError(err instanceof Error ? err.message : "Could not load appointments.");
      }
    } finally {
      if (current === sequence.current && mounted.current) setLoading(false);
    }
  }, [role, campusId, mode, date, status, slotPage, appointmentPage]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const timer = setInterval(() => { void refresh(true); }, 60_000);
    return () => clearInterval(timer);
  }, [refresh]);

  async function mutate(path, body, method = "POST", success = "Appointment updated.") {
    if (mutating.current) return false;
    mutating.current = true; setBusy(true); setError(""); setMessage("");
    try {
      await request(path, { method, ...(body === undefined || method === "DELETE" ? {} : { body: JSON.stringify(body) }) });
      if (mounted.current) { setMessage(success); await refresh(); }
      return true;
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "The change could not be saved.");
      return false;
    } finally {
      mutating.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return { campuses, slots, appointments, calendar, weeklySchedules, availabilityBlocks, loading, busy, error, message, refresh, mutate,
    campusId, setCampusId, mode, setMode, date, setDate, status, setStatus,
    slotPage, setSlotPage, appointmentPage, setAppointmentPage };
}
