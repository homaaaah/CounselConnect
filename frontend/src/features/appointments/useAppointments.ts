import { useCallback, useEffect, useRef, useState } from "react";
import { request } from "../../services/apiClient";

export type AppointmentMode = "ONLINE" | "FACE_TO_FACE";
export interface Campus { campus_id: number; campus_name: string; guidance_office_location: string | null }
export interface Slot {
  slot_id: number; counselor_user_id: number; counselor_name: string; campus_id: number; campus_name: string;
  guidance_office_location: string | null; delivery_mode: AppointmentMode | "BOTH";
  starts_at: string; ends_at: string; status: "AVAILABLE" | "RESERVED";
}
export interface Appointment {
  appointment_id: number; student_user_id: number; student_name: string; counselor_user_id: number;
  counselor_name: string; availability_slot_id: number; campus_id: number; campus_name: string;
  starts_at: string; ends_at: string; appointment_mode: AppointmentMode; meeting_location: string | null;
  conversation_id: number | null; status: "PENDING" | "CONFIRMED" | "COMPLETED" | "CANCELLED" | "REJECTED" | "NO_SHOW";
  rejection_note: string | null; created_at: string; updated_at: string;
}
interface Page<T> { items: T[]; page: number; page_size: number; total: number }
export interface CalendarDay { calendar_date: string; is_weekday: boolean; is_blocked: boolean; available_times: string[] }
export interface CalendarData { timezone: string; business_hours: string; days: CalendarDay[] }
export interface WeeklySchedule {
  weekly_schedule_id: number; counselor_user_id: number; campus_id: number; day_of_week: number;
  start_time: string; end_time: string; slot_duration_minutes: number; delivery_mode: AppointmentMode | "BOTH";
  is_active: boolean; created_at: string; updated_at: string;
}
export interface AvailabilityBlock {
  availability_block_id: number; counselor_user_id: number; starts_at: string; ends_at: string;
  is_all_day: boolean; reason: string | null; created_at: string; updated_at: string;
}
export const formatSchedule = (value: string) => new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila", dateStyle: "medium", timeStyle: "short",
}).format(new Date(value));
export const manilaInputToUTC = (value: string) => new Date(value + ":00+08:00").toISOString();

export function useAppointments(role = "") {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [slots, setSlots] = useState<Page<Slot>>({ items: [], page: 1, page_size: 20, total: 0 });
  const [appointments, setAppointments] = useState<Page<Appointment>>({ items: [], page: 1, page_size: 20, total: 0 });
  const [calendar, setCalendar] = useState<CalendarData | null>(null);
  const [weeklySchedules, setWeeklySchedules] = useState<WeeklySchedule[]>([]);
  const [availabilityBlocks, setAvailabilityBlocks] = useState<AvailabilityBlock[]>([]);
  const [campusId, setCampusId] = useState("");
  const [mode, setMode] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState("");
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
    if (date) {
      params.set("starts_after", new Date(date + "T00:00:00+08:00").toISOString());
      params.set("ends_before", new Date(new Date(date + "T00:00:00+08:00").getTime() + 86400000).toISOString());
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
      const calendarData = await request<CalendarData>("/calendar?" + calendarParams, { headers });
      const isCounselor = role === "COUNSELOR";
      const [campusData, slotData, appointmentData, scheduleData, blockData] = await Promise.all([
        request<Page<Campus>>("/accounts/campuses", { headers }),
        request<Page<Slot>>("/availability-slots?" + params, { headers }),
        request<Page<Appointment>>("/appointments?" + appParams, { headers }),
        isCounselor ? request<WeeklySchedule[]>("/weekly-schedules", { headers }) : Promise.resolve([] as WeeklySchedule[]),
        isCounselor ? request<AvailabilityBlock[]>("/availability-blocks", { headers }) : Promise.resolve([] as AvailabilityBlock[]),
      ]);
      if (current !== sequence.current || !mounted.current) return;
      setCampuses(campusData.items); setSlots(slotData); setAppointments(appointmentData); setCalendar(calendarData);
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

  async function mutate(path: string, body?: unknown, method = "POST", success = "Appointment updated.") {
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
