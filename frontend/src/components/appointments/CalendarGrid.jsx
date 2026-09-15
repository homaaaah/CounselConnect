import { useEffect, useState } from "react";
import { manilaToday } from "../../features/appointments";
import { secondaryClass } from "./ui.js";

/**
 * CalendarGrid — month grid of counselor availability from GET /calendar.
 * Extracted from the old AppointmentsPage CalendarView (2026-09-13) so the
 * HomePage booking modal and the counselor records view share one grid.
 * A day is bookable when it has real available times, is not blocked, and is
 * not past. Weekend dates stay disabled unless a counselor has scheduled
 * availability for them. The
 * 1s clock hides times whose start has already passed (client-side live
 * gap until the next server refresh). Clicking a bookable day reveals
 * that day's available times; onSelect/onPickTime notify the parent
 * (used by the booking modal), selection state lives here.
 */
export default function CalendarGrid({ calendar, onSelect, onPickTime, note }) {
  const [selected, setSelected] = useState(null);
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
  }));
  const byDate = new Map(days.map(day => [day.calendar_date, day]));
  const sortedDates = days.map(day => day.calendar_date).sort();
  const rangeStart = sortedDates[0];
  const rangeEnd = sortedDates[sortedDates.length - 1];
  const initialMonth = rangeStart ? rangeStart.slice(0, 7) : manilaToday().slice(0, 7);
  const [month, setMonth] = useState(initialMonth);
  useEffect(() => { setMonth(initialMonth); }, [initialMonth]);
  const monthStart = month + "-01";
  // Monday-based first cell of the displayed month (ISO weekday: Mon=1..Sun=7).
  const firstWeekday = new Date(monthStart + "T00:00:00").getDay();
  const leadingBlanks = (firstWeekday + 6) % 7;
  const monthDays = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)), 0).getDate();
  const cellDates = Array.from({ length: leadingBlanks + monthDays }, (_, i) =>
    i < leadingBlanks ? null : month + "-" + String(i - leadingBlanks + 1).padStart(2, "0"));
  const today = manilaToday();
  // The loaded range spans ~30 days, so at most two adjacent months have data.
  const hasData = (m) => Boolean(rangeStart && rangeEnd && m >= rangeStart.slice(0, 7) && m <= rangeEnd.slice(0, 7));
  const shiftMonth = (delta) => {
    const next = new Date(Number(month.slice(0, 4)), Number(month.slice(5, 7)) - 1 + delta, 1);
    setMonth(next.getFullYear() + "-" + String(next.getMonth() + 1).padStart(2, "0"));
  };
  const selectedDay = selected ? byDate.get(selected) : undefined;
  const monthTitle = new Date(monthStart + "T00:00:00").toLocaleDateString("en-PH", { month: "long", year: "numeric" });
  return <div>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="text-base font-medium">{monthTitle}</h3>
        <p className="mt-1 text-xs text-slate-500">{calendar?.business_hours || "Availability set by counselors"} · Philippine time</p></div>
      <div className="flex items-center gap-2">
        <button type="button" aria-label="Previous month" disabled={!hasData(month) || month <= rangeStart.slice(0, 7)} onClick={() => shiftMonth(-1)} className={secondaryClass + " !px-2 !py-1"}>‹</button>
        <button type="button" aria-label="Next month" disabled={!hasData(month) || month >= rangeEnd.slice(0, 7)} onClick={() => shiftMonth(1)} className={secondaryClass + " !px-2 !py-1"}>›</button>
      </div>
    </div>
    <div className="mt-3 grid grid-cols-7 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 text-center text-xs font-medium text-slate-500">
      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(d => <div key={d} className="bg-white py-2">{d}</div>)}
    </div>
    <div className="grid grid-cols-7 gap-px overflow-hidden rounded-b-lg border border-t-0 border-slate-200 bg-slate-200">
      {cellDates.map((cellDate, i) => {
        if (cellDate === null) return <div key={"blank" + i} className="min-h-20 bg-slate-50/50" />;
        const day = byDate.get(cellDate);
        const weekendWithoutAvailability = day && !day.is_weekday && day.available_times.length === 0;
        const state = !day ? "outofrange" : day.is_past ? "past" : day.is_blocked ? "blocked" : weekendWithoutAvailability ? "weekend" : "open";
        const bookable = day && !day.is_past && !day.is_blocked && !weekendWithoutAvailability;
        const isToday = cellDate === today;
        const isSelected = cellDate === selected;
        const label = !day ? "" : day.is_past ? "Already passed" : day.is_blocked ? "Unavailable" : weekendWithoutAvailability ? "Weekend" : day.available_times.length === 0 ? "No available time slots" : `${day.available_times.length} times available`;
        return <button key={cellDate} type="button" disabled={!bookable}
          onClick={() => { setSelected(cellDate); onSelect?.(cellDate); }}
          aria-label={cellDate + " — " + label}
          className={`group min-h-20 bg-white p-1.5 text-left transition-colors ${!bookable ? "cursor-default" : "hover:bg-emerald-50"} ${state === "past" ? "text-slate-300" : state === "blocked" ? "bg-red-50" : state === "weekend" ? "bg-slate-50 text-slate-400" : ""} ${isSelected ? "ring-2 ring-inset ring-emerald-600" : ""}`}>
          <span className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${isToday ? "bg-emerald-600 text-white" : ""}`}>{Number(cellDate.slice(8))}</span>
          {day && !day.is_past && !weekendWithoutAvailability && !day.is_blocked && <p className="mt-1 hidden truncate text-[10px] font-medium text-emerald-700 sm:block">
            {day.available_times.length > 0 ? day.available_times.length + " open" : "No times left"}</p>}
          {day && (day.is_past || day.is_blocked || weekendWithoutAvailability) && <p className="mt-1 hidden truncate text-[10px] text-slate-400 sm:block">{day.is_blocked ? "Blocked" : day.is_past ? "Passed" : "—"}</p>}
        </button>;
      })}
    </div>
    {selectedDay && !selectedDay.is_blocked && !selectedDay.is_past && <div className="mt-5 rounded-lg bg-slate-50 p-4">
      <p className="text-sm font-medium">Times for {selectedDay.calendar_date}</p>
      <div className="mt-3 flex flex-wrap gap-2">{selectedDay.available_times.map(time =>
        <button key={time} type="button" className={secondaryClass} onClick={() => onPickTime?.(selectedDay.calendar_date, time)}>{time}</button>)}</div>
      {selectedDay.available_times.length === 0
        ? <p className="mt-3 text-sm text-amber-700">There are no available appointment time slots for this date. Please select another date.</p>
        : <p className="mt-3 text-xs text-slate-500">{note || "Select a time to continue."}</p>}
    </div>}
  </div>;
}
