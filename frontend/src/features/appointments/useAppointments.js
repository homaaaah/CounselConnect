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

const SELECTED_DATE_SLOT_PAGE_SIZE = 100;
const VALIDATION_FIELD_LABELS = {
  availability_slot_id: "appointment time",
  appointment_mode: "session mode",
  concern_categories: "support topics",
  concern_details: "support details",
};

function mutationErrorMessage(error) {
  if (error?.code === "VALIDATION_ERROR" && Array.isArray(error.details?.fields)) {
    const fields = [...new Set(error.details.fields.map((field) => {
      const location = Array.isArray(field?.loc) ? field.loc : [];
      const name = location.at(-1);
      return VALIDATION_FIELD_LABELS[name] ?? "booking details";
    }))];
    if (fields.length) {
      return `Request validation failed. Please check your ${fields.join(", ")}.`;
    }
  }
  return error instanceof Error ? error.message : "The change could not be saved.";
}

/**
 * initialStatus seeds the records filter (e.g. "CONFIRMED" default on the
 * appointments page); empty string loads all statuses.
 */
export function useAppointments(role = "", initialStatus = "") {
  const [campuses, setCampuses] = useState([]);
  const [bookingCounselors, setBookingCounselors] = useState([]);
  const [bookingCounselorsError, setBookingCounselorsError] = useState("");
  const [counselorUserId, setCounselorUserId] = useState("");
  const [slots, setSlots] = useState({ items: [], page: 1, page_size: 20, total: 0 });
  const [appointments, setAppointments] = useState({ items: [], page: 1, page_size: 20, total: 0 });
  const [calendar, setCalendar] = useState(null);
  const [calendarMonth, setCalendarMonth] = useState(() => manilaToday().slice(0, 7));
  const [weeklySchedules, setWeeklySchedules] = useState([]);
  const [availabilityBlocks, setAvailabilityBlocks] = useState([]);
  const [campusId, setCampusId] = useState("");
  const [mode, setMode] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState(initialStatus);
  const [slotPage, setSlotPage] = useState(1);
  const [appointmentPage, setAppointmentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [recordsLoading, setRecordsLoading] = useState(true);
  const [availabilityBlocksLoading, setAvailabilityBlocksLoading] = useState(role === "COUNSELOR");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recordsError, setRecordsError] = useState("");
  const [availabilityBlocksError, setAvailabilityBlocksError] = useState("");
  const [message, setMessage] = useState("");
  const sequence = useRef(0);
  const mounted = useRef(true);
  const mutating = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; sequence.current++; }; }, []);

  const refresh = useCallback(async (background = false) => {
    const current = ++sequence.current;
    const isCounselor = role === "COUNSELOR";
    setLoading(true);
    if (!background) setRecordsLoading(true);
    if (isCounselor && !background) setAvailabilityBlocksLoading(true);
    setError("");
    const todayManila = manilaToday();
    const effectiveDate = date && date >= todayManila ? date : "";
    // A calendar time may represent slots from several counselors. Once the
    // visitor chooses a date, load every page for that date so the modal can
    // offer each matching slot instead of treating page one as exhaustive.
    const selectedDatePage = effectiveDate ? 1 : slotPage;
    const selectedDatePageSize = effectiveDate ? SELECTED_DATE_SLOT_PAGE_SIZE : 20;
    const params = new URLSearchParams({
      page: String(selectedDatePage),
      page_size: String(selectedDatePageSize),
    });
    if (campusId) params.set("campus_id", campusId);
    if (mode) params.set("appointment_mode", mode);
    if (role === "STUDENT" && counselorUserId) params.set("counselor_user_id", counselorUserId);
    if (effectiveDate) {
      params.set("starts_after", new Date(effectiveDate + "T00:00:00+08:00").toISOString());
      params.set("ends_before", new Date(new Date(effectiveDate + "T00:00:00+08:00").getTime() + 86400000).toISOString());
    }
    const appParams = new URLSearchParams({ page: String(appointmentPage), page_size: "20" });
    if (status) appParams.set("status", status);
    const [calendarYear, calendarMonthNumber] = calendarMonth.split("-").map(Number);
    const calendarStart = `${calendarMonth}-01`;
    const calendarEndDate = new Date(0);
    calendarEndDate.setUTCHours(0, 0, 0, 0);
    calendarEndDate.setUTCFullYear(calendarYear, calendarMonthNumber, 0);
    const calendarEnd = calendarEndDate.toISOString().slice(0, 10);
    const calendarParams = new URLSearchParams({ start_date: calendarStart, end_date: calendarEnd });
    if (role === "STUDENT" && counselorUserId) calendarParams.set("counselor_user_id", counselorUserId);
    const headers = background ? { "X-Background-Refresh": "1" } : undefined;
    try {
      const [calendarResult, campusResult, firstSlotResult, appointmentsResult, schedulesResult, blocksResult, counselorsResult] = await Promise.allSettled([
        request("/calendar?" + calendarParams, { headers }),
        request("/accounts/campuses", { headers }),
        request("/availability-slots?" + params, { headers }),
        request("/appointments?" + appParams, { headers }),
        isCounselor ? request("/weekly-schedules", { headers }) : Promise.resolve([]),
        isCounselor ? request("/availability-blocks", { headers }) : Promise.resolve([]),
        role === "STUDENT" ? request("/booking-counselors", { headers }) : Promise.resolve([]),
      ]);
      let slotData = null;
      let availabilityError = "";
      if (firstSlotResult.status === "fulfilled") {
        slotData = firstSlotResult.value;
      } else {
        availabilityError = "Could not load available appointment times.";
      }
      if (slotData && effectiveDate) {
        const validFirstPage = Array.isArray(slotData.items)
          && Number.isInteger(slotData.total) && slotData.total >= 0
          && slotData.page === 1 && slotData.page_size === selectedDatePageSize
          && slotData.items.length === Math.min(slotData.total, selectedDatePageSize)
          && new Set(slotData.items.map((item) => item.slot_id)).size === slotData.items.length;
        if (!validFirstPage) {
          availabilityError = "The availability response was incomplete. Retry loading this date.";
          slotData = null;
        }
      }
      if (slotData && effectiveDate && slotData.total > slotData.items.length) {
        const firstPage = slotData;
        const extraPages = Math.ceil(slotData.total / selectedDatePageSize) - 1;
        const extraSlots = await Promise.allSettled(
          Array.from({ length: extraPages }, (_, index) => {
            const pageParams = new URLSearchParams(params);
            pageParams.set("page", String(index + 2));
            return request("/availability-slots?" + pageParams, { headers });
          })
        );
        const pagesAreComplete = extraSlots.every((result, index) => {
          if (result.status !== "fulfilled") return false;
          const page = result.value;
          return Array.isArray(page.items)
            && page.page === index + 2
            && page.page_size === selectedDatePageSize
            && page.total === firstPage.total
            && page.items.length <= selectedDatePageSize;
        });
        const allItems = pagesAreComplete
          ? firstPage.items.concat(...extraSlots.map((result) => result.value.items))
          : [];
        const uniqueSlotIds = new Set(allItems.map((item) => item.slot_id));
        if (pagesAreComplete && allItems.length === firstPage.total
            && uniqueSlotIds.size === allItems.length) {
          slotData = { ...firstPage, items: allItems };
        } else {
          availabilityError = "Could not load a complete availability list for that date. Retry before choosing a slot.";
          slotData = null;
        }
      }
      if (current !== sequence.current || !mounted.current) return;
      if (calendarResult.status === "fulfilled") setCalendar(calendarResult.value);
      else availabilityError ||= "Could not load the availability calendar.";
      if (campusResult.status === "fulfilled") setCampuses(campusResult.value.items);
      else availabilityError ||= "Could not load campus information.";
      if (counselorsResult.status === "fulfilled") {
        setBookingCounselors(counselorsResult.value);
        setBookingCounselorsError("");
      } else if (role === "STUDENT") {
        setBookingCounselorsError(counselorsResult.reason instanceof Error
          ? counselorsResult.reason.message : "Could not load Counselors.");
      }
      if (slotData) {
        // A slot becomes unbookable the moment its start passes; the backend
        // already excludes past slots, this covers the gap until refresh.
        const stillFuture = slotData.items.filter(slot => new Date(slot.starts_at).getTime() > Date.now());
        setSlots({ ...slotData, items: stillFuture, total: slotData.total });
      } else if (effectiveDate) {
        // Never leave previous or partial date results selectable after a failed read.
        setSlots({ items: [], page: 1, page_size: SELECTED_DATE_SLOT_PAGE_SIZE, total: 0 });
      }
      if (appointmentsResult.status === "fulfilled") {
        setAppointments(appointmentsResult.value);
        setRecordsError("");
      } else {
        setRecordsError(appointmentsResult.reason instanceof Error
          ? appointmentsResult.reason.message : "Could not load appointment records.");
      }
      if (schedulesResult.status === "fulfilled") setWeeklySchedules(schedulesResult.value);
      else if (isCounselor) availabilityError ||= "Could not load weekly availability.";
      if (blocksResult.status === "fulfilled") {
        setAvailabilityBlocks(blocksResult.value);
        setAvailabilityBlocksError("");
      } else if (isCounselor) {
        setAvailabilityBlocksError(blocksResult.reason instanceof Error
          ? blocksResult.reason.message : "Could not load unavailable times.");
      }
      setError(availabilityError);
    } catch (err) {
      if (current === sequence.current && mounted.current) setError(
        err instanceof Error ? err.message : "Could not load appointment availability."
      );
    } finally {
      if (current === sequence.current && mounted.current) {
        setLoading(false);
        setRecordsLoading(false);
        if (isCounselor) setAvailabilityBlocksLoading(false);
      }
    }
  }, [role, campusId, mode, date, status, slotPage, appointmentPage, calendarMonth, counselorUserId]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const onAppointmentUpdated = () => { void refresh(true); };
    window.addEventListener("appointment-updated", onAppointmentUpdated);
    return () => window.removeEventListener("appointment-updated", onAppointmentUpdated);
  }, [refresh]);
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
      if (mounted.current) setError(mutationErrorMessage(err));
      return false;
    } finally {
      mutating.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return { campuses, bookingCounselors, bookingCounselorsError, counselorUserId, setCounselorUserId, slots, appointments, calendar, calendarMonth, setCalendarMonth, weeklySchedules, availabilityBlocks, loading, recordsLoading, availabilityBlocksLoading, busy, error, recordsError, availabilityBlocksError, message, refresh, mutate,
    campusId, setCampusId, mode, setMode, date, setDate, status, setStatus,
    slotPage, setSlotPage, appointmentPage, setAppointmentPage };
}
