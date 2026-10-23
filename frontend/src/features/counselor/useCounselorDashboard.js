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
    // GET /appointments documents only status/page/page_size, so page through
    // it rather than sending unsupported date filters.
    let cancelled = false;
    setLoading(true);
    setError("");
    const today = manilaToday();

    const load = async () => {
      const pageSize = 100;
      const collected = [];
      let page = 1;
      let total = Infinity;
      while (!cancelled && page <= 20) {
        const data = await request(`/appointments?page=${page}&page_size=${pageSize}`);
        const batch = data?.items ?? [];
        collected.push(...batch);
        total = typeof data?.total === "number" ? data.total : collected.length;
        if (batch.length < pageSize || collected.length >= total) break;
        page += 1;
      }
      if (cancelled) return;
      setItems(collected
        .filter((appointment) => manilaDay(appointment.starts_at) === today)
        .sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)));
    };

    load()
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
