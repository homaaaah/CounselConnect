/**
 * useProfileChangeRequests — Superadmin queue of pending profile-edit requests
 * (ADR-032). Enabled only for the Superadmin Users page.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

function toError(err, fallback) {
  return err instanceof ApiError ? err.message : fallback;
}

export function useProfileChangeRequests(enabled = true) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(Boolean(enabled));
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError("");
    try {
      const data = await request("/profile-change-requests?status=PENDING");
      if (mounted.current) setItems(data?.items ?? []);
    } catch (err) {
      if (mounted.current) setError(toError(err, "Could not load edit requests."));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    void load();
  }, [load]);

  async function approve(changeRequestId) {
    setBusyId(changeRequestId);
    try {
      await request(`/profile-change-requests/${changeRequestId}/approve`, { method: "POST" });
      await load();
      return { success: true };
    } catch (err) {
      return { success: false, message: toError(err, "Could not approve this request.") };
    } finally {
      if (mounted.current) setBusyId(null);
    }
  }

  async function reject(changeRequestId, reason) {
    setBusyId(changeRequestId);
    try {
      await request(`/profile-change-requests/${changeRequestId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      });
      await load();
      return { success: true };
    } catch (err) {
      return { success: false, message: toError(err, "Could not reject this request.") };
    } finally {
      if (mounted.current) setBusyId(null);
    }
  }

  return { items, loading, error, busyId, load, approve, reject };
}
