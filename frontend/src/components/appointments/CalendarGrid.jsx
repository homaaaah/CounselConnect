import { useEffect, useId, useState } from "react";
import { manilaToday } from "../../features/appointments";
import { secondaryClass } from "./ui.js";

function localDate(year, monthIndex, day = 1) {
  const value = new Date(0);
  value.setHours(0, 0, 0, 0);
  value.setFullYear(year, monthIndex, day);
  return value;
}

function timeLabel(value) {
  if (!value) return "";
  const [hourText, minuteText] = value.slice(0, 5).split(":");
  const hour = Number(hourText);
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}:${minuteText} ${suffix}`;
}

/**
 * CalendarGrid — month grid of counselor availability from GET /calendar.
 * Extracted from the old AppointmentsPage CalendarView (2026-09-13) so the
 * HomePage booking modal and the counselor records view share one grid.
 * A day is bookable when it has real available times, is not blocked, and is
 * not past. Weekend dates follow the same selection rules as weekdays; a day
 * without availability can be selected to show that no times are offered. The
 * 1s clock hides times whose start has already passed (client-side live
 * gap until the next server refresh). Clicking a bookable day reveals
 * that day's available times; onSelect/onPickTime notify the parent
 * (used by the booking modal), selection state lives here.
 *
 * variant="modal" opts into the booking-modal look and week order. Every
 * extra hook class it adds (booking-day, booking-time, …) is only styled
 * under `.booking-calendar`, so the default rendering — used by the
 * Counselor availability panel — is visually unchanged.
 */
export default function CalendarGrid({ calendar, month: visibleMonth, onMonthChange, onRetry, loading = false, onSelect, onPickTime, variant, counselorView = false }) {
  const inModal = variant === "modal";
  const monthInputId = useId();
  const [selected, setSelected] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = setInterval(update, 1000);
    window.addEventListener("focus", update);
    return () => { clearInterval(timer); window.removeEventListener("focus", update); };
  }, []);
  const currentTime = Math.max(now, Date.now());
  const days = (Array.isArray(calendar?.days) ? calendar.days : []).map(day => ({
    ...day,
    is_past: day.is_past || new Date(day.calendar_date + "T00:00:00+08:00").getTime() + 86400000 <= currentTime,
    available_times: day.available_times.filter(time =>
      new Date(day.calendar_date + "T" + time + ":00+08:00").getTime() > currentTime),
    available_slots: (Array.isArray(day.available_slots) ? day.available_slots : [])
      .map(slot => ({ ...slot, start_time: slot.start_time.slice(0, 5), end_time: slot.end_time.slice(0, 5) }))
      .filter(slot => new Date(day.calendar_date + "T" + slot.start_time + ":00+08:00").getTime() > currentTime),
    booked_slots: (Array.isArray(day.booked_slots) ? day.booked_slots : []).map(slot => ({
      ...slot, start_time: slot.start_time.slice(0, 5), end_time: slot.end_time.slice(0, 5),
    })),
  }));
  const byDate = new Map(days.map(day => [day.calendar_date, day]));
  const sortedDates = days.map(day => day.calendar_date).sort();
  const rangeStart = sortedDates[0];
  const rangeEnd = sortedDates[sortedDates.length - 1];
  const initialMonth = rangeStart ? rangeStart.slice(0, 7) : manilaToday().slice(0, 7);
  const [localMonth, setLocalMonth] = useState(initialMonth);
  useEffect(() => { if (!visibleMonth) setLocalMonth(initialMonth); }, [initialMonth, visibleMonth]);
  const month = visibleMonth || localMonth;
  useEffect(() => { setSelected(null); setPickedTime(null); }, [month]);
  const monthStart = month + "-01";
  const [monthYear, monthNumber] = month.split("-").map(Number);
  // The modal variant starts the week on Sunday (matching the design); the
  // default keeps the existing Monday-first grid.
  const weekdayLabels = inModal
    ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  // First cell of the displayed month (ISO weekday: Mon=1..Sun=7).
  const firstWeekday = localDate(monthYear, monthNumber - 1).getDay();
  const leadingBlanks = inModal ? firstWeekday : (firstWeekday + 6) % 7;
  const monthDays = localDate(monthYear, monthNumber, 0).getDate();
  const cellDates = Array.from({ length: leadingBlanks + monthDays }, (_, i) =>
    i < leadingBlanks ? null : month + "-" + String(i - leadingBlanks + 1).padStart(2, "0"));
  const today = manilaToday();
  const shiftMonth = (delta) => {
    const next = localDate(monthYear, monthNumber - 1 + delta, 1);
    const nextMonth = String(next.getFullYear()).padStart(4, "0") + "-" + String(next.getMonth() + 1).padStart(2, "0");
    if (onMonthChange) onMonthChange(nextMonth);
    else setLocalMonth(nextMonth);
  };
  const chooseMonth = (nextMonth) => {
    if (!nextMonth) return;
    if (onMonthChange) onMonthChange(nextMonth);
    else setLocalMonth(nextMonth);
  };
  const monthLoaded = days.some(day => day.calendar_date.startsWith(month + "-"));
  const canBrowseWithoutFetching = !onMonthChange && Boolean(rangeStart && rangeEnd);
  const selectedDay = selected ? byDate.get(selected) : undefined;
  const monthTitle = localDate(monthYear, monthNumber - 1).toLocaleDateString("en-PH", { month: "long", year: "numeric" });
  const navBtnClass = inModal ? "booking-nav-btn" : secondaryClass + " !px-2 !py-1";
  const selectedDateLabel = selectedDay
    ? new Date(selectedDay.calendar_date + "T00:00:00+08:00").toLocaleDateString("en-PH",
        { timeZone: "Asia/Manila", weekday: "long", month: "short", day: "numeric", year: "numeric" })
    : "";
  return <div className={inModal ? "booking-calendar" : undefined}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className={"text-base font-medium" + (inModal ? " booking-month-title" : "")}>{monthTitle}</h3>
        <p className="mt-1 text-xs text-slate-500">{calendar?.business_hours || "Availability set by counselors"} · Philippine time</p></div>
      <div className="flex items-center gap-2">
        <button type="button" aria-label="Previous month" disabled={canBrowseWithoutFetching && month <= rangeStart.slice(0, 7)} onClick={() => shiftMonth(-1)} className={navBtnClass}>‹</button>
        <button type="button" aria-label="Next month" disabled={canBrowseWithoutFetching && month >= rangeEnd.slice(0, 7)} onClick={() => shiftMonth(1)} className={navBtnClass}>›</button>
        <label className="sr-only" htmlFor={monthInputId}>Jump to month and year</label>
        <input id={monthInputId} aria-label="Jump to month and year"
          type="month" value={month} onChange={event => chooseMonth(event.target.value)}
          className="max-w-40 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700" />
        {month !== today.slice(0, 7) && <button type="button" className={navBtnClass} onClick={() => chooseMonth(today.slice(0, 7))}>Today</button>}
      </div>
    </div>
    {!monthLoaded && <p role={loading ? "status" : "alert"} className="mt-3 text-sm text-slate-500">
      {loading ? `Loading availability for ${monthTitle}…` : "Availability for this month could not be loaded."}
      {!loading && onRetry && <button type="button" className="ml-2 underline" onClick={() => void onRetry()}>Retry</button>}
    </p>}
    <div className="booking-weekdays mt-3 grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 text-center text-xs font-medium text-slate-500">
      {weekdayLabels.map(d => <div key={d} className="booking-weekday bg-white py-2">{d}</div>)}
    </div>
    <div className="booking-days grid grid-cols-7 gap-px overflow-hidden rounded-b-lg border border-t-0 border-slate-200 bg-slate-200">
      {cellDates.map((cellDate, i) => {
        if (cellDate === null) return <div key={"blank" + i} className="min-h-20 bg-slate-50/50" />;
        const day = byDate.get(cellDate);
        const state = !day ? "outofrange" : day.is_past ? "past" : day.is_blocked ? "blocked" : "open";
        const bookable = day && !day.is_past && !day.is_blocked;
        const isToday = cellDate === today;
        const isSelected = cellDate === selected;
        const bookedSlots = day?.booked_slots ?? [];
        const hasBookedAppointments = counselorView && bookedSlots.length > 0;
        const label = !day ? "" : day.is_past ? "Already passed" : day.is_blocked ? "Unavailable"
          : counselorView
            ? (bookedSlots.length ? `${bookedSlots.length} booked appointment${bookedSlots.length === 1 ? "" : "s"}` : "No booked appointments")
            : (day.available_times.length === 0 ? "No available time slots" : `${day.available_times.length} times available`);
        return <div key={cellDate} className="booking-day-cell flex min-w-0 flex-col bg-white">
          <button type="button" disabled={!bookable} aria-pressed={isSelected}
            onClick={() => { setSelected(cellDate); setPickedTime(null); onSelect?.(cellDate); }}
            aria-label={cellDate + " — " + label}
            className={`booking-day group min-h-20 w-full bg-white p-1.5 text-left transition-colors ${!bookable ? "cursor-default" : "hover:bg-emerald-50"} ${state === "past" ? "text-slate-300" : state === "blocked" ? "bg-red-50" : ""} ${isSelected ? "booking-day--selected ring-2 ring-inset ring-emerald-600" : ""}`}>
            <span className="flex items-center justify-between gap-1">
              <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${isToday ? "bg-emerald-600 text-white" : ""}`}>{Number(cellDate.slice(8))}</span>
              {hasBookedAppointments && <span className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-amber-500" title="Booked appointment" aria-label="Booked appointment" />}
            </span>
            {inModal && day && !day.is_past && !day.is_blocked && <p className="mt-1 hidden truncate text-[10px] font-medium text-emerald-700 sm:block">
              {day.available_times.length > 0 ? "Available" : "No times"}</p>}
            {day && (day.is_past || day.is_blocked) && <p className="mt-1 hidden truncate text-[10px] text-slate-400 sm:block">{day.is_blocked ? "Blocked" : "Passed"}</p>}
          </button>
        </div>;
      })}
    </div>
    {selectedDay && !selectedDay.is_blocked && !selectedDay.is_past && <div className="booking-times-panel mt-5 rounded-lg bg-slate-50 p-4">
      <p className="booking-times-title text-sm font-medium">{counselorView ? "Booked Appointments" : "Available Times"}</p>
      {selectedDateLabel && <p className="booking-times-date">{selectedDateLabel}</p>}
      {!counselorView
        ? <>
            <div className="booking-times-list mt-3 flex flex-col gap-2">{slotsForDay(selectedDay).map(slot =>
              <button key={slot.start_time + "-" + (slot.end_time || "start")} type="button"
                aria-pressed={pickedTime === slot.start_time}
                className={"booking-time " + secondaryClass + (pickedTime === slot.start_time ? " booking-time--selected" : "")}
                onClick={() => { setPickedTime(slot.start_time); onPickTime?.(selectedDay.calendar_date, slot.start_time); }}>
                <span>{timeLabel(slot.start_time)}{slot.end_time ? ` – ${timeLabel(slot.end_time)}` : ""}</span>
              </button>)}</div>
            {slotsForDay(selectedDay).length === 0
              ? <p className="mt-3 text-sm text-amber-700">There are no available appointment time slots for this date. Please select another date.</p>
              : <p className="booking-times-note mt-3 text-xs text-slate-500">Select a time to continue.</p>}
          </>
        : selectedDay.booked_slots.length > 0
          ? <div className="booking-times-list mt-3 flex flex-col gap-2" aria-label="Booked appointment times">
              {selectedDay.booked_slots.map(slot => <div key={slot.start_time + "-" + slot.end_time + "-" + slot.status}
                className="booking-time flex h-[52px] w-full items-center justify-between gap-3 rounded-[11px] border border-[#edf0f3] bg-white px-[15px] text-sm font-bold text-[#172033]">
                <span>{timeLabel(slot.start_time)} – {timeLabel(slot.end_time)}</span>
                <span className={"rounded-full px-2 py-1 text-xs font-semibold " + (slot.status === "PENDING" ? "bg-amber-50 text-amber-700" : "bg-emerald-50 text-emerald-700")}>
                  {slot.status === "PENDING" ? "Pending" : "Confirmed"}
                </span>
              </div>)}
            </div>
          : <p className="mt-3 text-sm text-slate-500">No booked appointments for this date.</p>}
    </div>}
  </div>;
}

function slotsForDay(day) {
  return day.available_slots.length > 0
    ? day.available_slots
    : day.available_times.map(time => ({ start_time: time, end_time: null }));
}
