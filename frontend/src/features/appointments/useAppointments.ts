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
export const formatSchedule = (value: string) => new Intl.DateTimeFormat("en-PH", {
  timeZone: "Asia/Manila", dateStyle: "medium", timeStyle: "short",
}).format(new Date(value));
export const manilaInputToUTC = (value: string) => new Date(value + ":00+08:00").toISOString();

export function useAppointments() {
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [slots, setSlots] = useState<Page<Slot>>({ items: [], page: 1, page_size: 20, total: 0 });
  const [appointments, setAppointments] = useState<Page<Appointment>>({ items: [], page: 1, page_size: 20, total: 0 });
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

  const refresh = useCallback(async () => {
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
      const [campusData, slotData, appointmentData] = await Promise.all([
        request<Page<Campus>>("/accounts/campuses"),
        request<Page<Slot>>("/availability-slots?" + params),
        request<Page<Appointment>>("/appointments?" + appParams),
      ]);
      if (current !== sequence.current || !mounted.current) return;
      setCampuses(campusData.items); setSlots(slotData); setAppointments(appointmentData);
    } catch (err) {
      if (current === sequence.current && mounted.current) {
        setSlots({ items: [], page: slotPage, page_size: 20, total: 0 });
        setAppointments({ items: [], page: appointmentPage, page_size: 20, total: 0 });
        setError(err instanceof Error ? err.message : "Could not load appointments.");
      }
    } finally {
      if (current === sequence.current && mounted.current) setLoading(false);
    }
  }, [campusId, mode, date, status, slotPage, appointmentPage]);
  useEffect(() => { void refresh(); }, [refresh]);

  async function mutate(path: string, body?: unknown, method = "POST", success = "Appointment updated.") {
    if (mutating.current) return false;
    mutating.current = true; setBusy(true); setError(""); setMessage("");
    try {
      await request(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
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
  return { campuses, slots, appointments, loading, busy, error, message, refresh, mutate,
    campusId, setCampusId, mode, setMode, date, setDate, status, setStatus,
    slotPage, setSlotPage, appointmentPage, setAppointmentPage };
}
