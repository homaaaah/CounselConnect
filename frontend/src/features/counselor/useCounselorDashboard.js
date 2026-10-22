/**
 * useCounselorDashboard — data seam for the Counselor dashboard.
 *
 * Only the appointment figures have a documented source today:
 *   - GET /appointments        -> total (KPI) via the existing useAppointmentCount
 *                                 hook, and the first page of records used to
 *                                 derive today's rows.
 *   - GET /accounts/students   -> student total via useStudentCount.
 *
 * Everything else the dashboard shows (emergency cases, solved/ongoing case
 * counts, weekly appointment volume, case distribution) has NO documented
 * endpoint yet, so those fields resolve to null/[]. Their widgets render an
 * empty state and will populate automatically once a source is wired here.
 *
 * Do not add new endpoints here without a documented contract
 * (docs/API_CONTRACT.md).
 */
import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";
import { manilaToday, useAppointmentCount } from "../appointments";
import { useStudentCount } from "../accounts";

// Records have no server date filter yet, so read one page and keep today's rows.
const TODAY_PAGE_SIZE = 50;

/** Manila calendar date (YYYY-MM-DD) for a UTC ISO timestamp. */
const manilaDay = (value) =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date(value));

export function useCounselorDashboard(user) {
  const appointments = useAppointmentCount();
  const students = useStudentCount();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Single place to swap for a dedicated "today" endpoint later.
    let cancelled = false;
    setLoading(true);
    setError("");
    request(`/appointments?page=1&page_size=${TODAY_PAGE_SIZE}`)
      .then((data) => {
        if (cancelled) return;
        const today = manilaToday();
        setItems((data?.items ?? [])
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

  return {
    appointments, // { total, loading, error }
    students,     // { total, loading, error }
    today: { items, loading, error },
    // No documented data source yet — widgets render an empty state.
    emergencies: null,
    solvedCases: null,
    ongoingCases: null,
    weeklyVolume: null,
    caseDistribution: null,
  };
}