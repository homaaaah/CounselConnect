/**
 * useCounselorDashboard — data seam for the Counselor dashboard.
 *
 * Documented sources only:
 *   - GET /appointments                 -> KPI total and today's rows via the
 *                                          documented starts_after/ends_before
 *                                          range filters.
 *   - GET /appointments?status=PENDING  -> pending-request KPI (same hook).
 *   - GET /accounts/students            -> student total via useStudentCount.
 *   - GET /appointments + range filters -> per-day volume for the current
 *                                          Manila week (Mon-Sun), excluding
 *                                          CANCELLED and REJECTED.
 *
 * Solved/ongoing case counts and case distribution have NO documented source
 * yet, so they resolve to null and their widgets keep an empty state.
 *
 * Every appointment read is self-scoped by the backend (a Counselor only
 * receives their own rows), so no center-wide series can be derived here.
 *
 * Do not add new endpoints here without a documented contract
 * (docs/API_CONTRACT.md).
 */
import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";
import { manilaToday, useAppointmentCount } from "../appointments";
import { useStudentCount } from "../accounts";

/** Manila calendar date (YYYY-MM-DD) for a UTC ISO timestamp. */
const manilaDay = (value) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date(value));

/** Shift a YYYY-MM-DD calendar date by whole days. */
const addDays = (day, days) => {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date + days)).toISOString().slice(0, 10);
};

/** Monday (YYYY-MM-DD) of the Manila week containing `day`. */
const mondayOf = (day) => {
  const [year, month, date] = day.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, date)).getUTCDay(); // 0 = Sunday
  return addDays(day, -((weekday + 6) % 7));
};

/** Manila-local midnight as a UTC ISO timestamp (range filters are UTC). */
const manilaMidnight = (day) => new Date(`${day}T00:00:00+08:00`).toISOString();

/** Whole-day offset of `day` from `start`, both YYYY-MM-DD calendar dates. */
const dayOffset = (start, day) =>
  Math.round((Date.parse(`${day}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86400000);

const PAGE_SIZE = 100;
const MAX_PAGES = 20;

/**
 * Read every page of a ranged appointment query.
 *
 * One page is not the complete set: the documented maximum is 100 records, so
 * a full page means "more may follow" until the envelope total is reached.
 */
async function fetchAllRows(range, isCancelled) {
  const rows = [];
  let page = 1;
  let total = Infinity;
  while (!isCancelled() && page <= MAX_PAGES) {
    const data = await request(`/appointments?page=${page}&page_size=${PAGE_SIZE}&${range}`);
    const batch = data?.items ?? [];
    rows.push(...batch);
    total = typeof data?.total === "number" ? data.total : rows.length;
    if (batch.length < PAGE_SIZE || rows.length >= total) break;
    page += 1;
  }
  return rows;
}

export function useCounselorDashboard(user) {
  const appointments = useAppointmentCount();
  const pendingRequests = useAppointmentCount("PENDING");
  const students = useStudentCount();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [weekly, setWeekly] = useState({ myCases: [], loading: true, error: "" });

  useEffect(() => {
    // Query the Manila-local day through the documented UTC range filters.
    let cancelled = false;
    setLoading(true);
    setError("");
    const today = manilaToday();
    const range = `starts_after=${encodeURIComponent(manilaMidnight(today))}`
      + `&ends_before=${encodeURIComponent(manilaMidnight(addDays(today, 1)))}`;

    fetchAllRows(range, () => cancelled)
      .then((rows) => {
        if (cancelled) return;
        setItems(rows
          .filter((appointment) => manilaDay(appointment.starts_at) === today)
          .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)));
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load today's appointments.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [user?.user_id]);

  useEffect(() => {
    // Weekly volume: Mon-Sun of the current Manila week. Future days stay 0.
    let cancelled = false;
    setWeekly({ myCases: [], loading: true, error: "" });
    const monday = mondayOf(manilaToday());
    const range = `starts_after=${encodeURIComponent(manilaMidnight(monday))}`
      + `&ends_before=${encodeURIComponent(manilaMidnight(addDays(monday, 7)))}`;

    fetchAllRows(range, () => cancelled)
      .then((rows) => {
        if (cancelled) return;
        const myCases = Array(7).fill(0);
        for (const appointment of rows) {
          // Cancelled/rejected appointments never happened, so they are not volume.
          if (appointment.status === "CANCELLED" || appointment.status === "REJECTED") continue;
          const index = dayOffset(monday, manilaDay(appointment.starts_at));
          if (index >= 0 && index < myCases.length) myCases[index] += 1;
        }
        setWeekly({ myCases, loading: false, error: "" });
      })
      .catch((err) => {
        // A failed read is an error, not an empty week.
        if (!cancelled) {
          setWeekly({
            myCases: [],
            loading: false,
            error: err instanceof Error ? err.message : "Could not load weekly appointment volume.",
          });
        }
      });
    return () => { cancelled = true; };
  }, [user?.user_id]);

  return {
    appointments,      // { total, loading, error }
    pendingRequests,   // { total, loading, error }
    students,          // { total, loading, error }
    today: { items, loading, error },
    weeklyVolume: weekly, // { myCases: number[7], loading, error }
    // No documented data source yet — widgets render an empty state.
    solvedCases: null,
    ongoingCases: null,
    caseDistribution: null,
  };
}
