import { useEffect, useState } from "react";
import { request } from "../../services/apiClient";

/**
 * useAppointmentCount — one GET /appointments call (no status filter) that
 * feeds the counselor dashboard's "Appointments" stat card with the
 * envelope's `total` (the counselor's own appointments across all statuses).
 *
 * TODO(backend): the dashboard's "Total users" card has NO documented
 * user-count endpoint in docs/API_CONTRACT.md yet, so it renders a
 * placeholder. When an endpoint is added, wire it here next to this hook
 * — the card in HomePage.jsx reads from this file only.
 */
export function useAppointmentCount() {
  const [total, setTotal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await request("/appointments");
        if (!cancelled) setTotal(data.total ?? 0);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load appointment count.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return { total, loading, error };
}
