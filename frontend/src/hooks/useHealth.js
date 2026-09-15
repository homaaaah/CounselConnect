/**
 * useHealth — demo hook proving frontend-to-backend connectivity.
 *
 * Calls GET /api/v1/health through the shared apiClient (snake_case stays
 * untouched in transport per NAMING_CONVENTIONS.md).
 */
import { useEffect, useState } from "react";
import { request } from "../services/apiClient";

export function useHealth() {
  const [status, setStatus] = useState("checking...");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    request("/health")
      .then((data) => {
        if (!cancelled) setStatus(data.status);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { status, error };
}
