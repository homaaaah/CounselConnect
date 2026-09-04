/**
 * useHealth — demo hook proving frontend-to-backend connectivity.
 *
 * Calls GET /api/v1/health through the shared apiClient (snake_case stays
 * untouched in transport per NAMING_CONVENTIONS.md).
 */
import { useEffect, useState } from "react";
import { request } from "../services/apiClient";

interface HealthResponse {
  status: string;
}

export function useHealth() {
  const [status, setStatus] = useState<string>("checking...");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    request<HealthResponse>("/health")
      .then((data: HealthResponse) => {
        if (!cancelled) setStatus(data.status);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { status, error };
}
