/**
 * useReviewerConsole — counselor review of registration applications
 * (DFD 1.3). Views the pending queue with applicant details, previews the
 * COR PDF, approves, or rejects with a required comment.
 *
 * Dev scaffold: uses the temporary reviewer key (X-Admin-Key) header until
 * ADR-P01 provides real COUNSELOR authentication.
 */
import { useCallback, useEffect, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

export interface PendingApplication {
  verification: {
    verification_id: number;
    status: string;
    submitted_at: string;
    decision_at: string | null;
    reviewed_by_user_id: number | null;
    reviewer_note: string | null;
    valid_until: string | null;
  };
  student: {
    user_id: number;
    email: string;
    first_name: string;
    middle_name: string | null;
    last_name: string;
    student_number?: string;
    year_level?: number;
    section?: string;
  };
  file: { file_id: number; size_bytes: number; expires_at: string } | null;
}

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function reviewerHeaders(key: string): Record<string, string> {
  return { "X-Admin-Key": key };
}

export function useReviewerConsole() {
  const [adminKey, setAdminKey] = useState(
    () => localStorage.getItem("cc_dev_admin_key") ?? ""
  );
  const [queue, setQueue] = useState<PendingApplication[]>([]);
  const [history, setHistory] = useState<PendingApplication[]>([]);
  const [historyFilter, setHistoryFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "warn"; text: string } | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    localStorage.setItem("cc_dev_admin_key", adminKey);
  }, [adminKey]);

  const refresh = useCallback(async () => {
    if (!adminKey) {
      setQueue([]);
      setHistory([]);
      return;
    }
    setLoading(true);
    try {
      const [pending, all] = await Promise.all([
        request<PendingApplication[]>("/enrollment-verifications/pending", {
          headers: reviewerHeaders(adminKey),
        }),
        request<PendingApplication[]>(
          historyFilter
            ? `/enrollment-verifications/history?status=${historyFilter}`
            : "/enrollment-verifications/history",
          { headers: reviewerHeaders(adminKey) }
        ),
      ]);
      setQueue(pending);
      setHistory(all);
      setMessage(null);
    } catch (err) {
      setQueue([]);
      setHistory([]);
      setMessage(
        err instanceof ApiError ? err.message : "Could not load the applications."
      );
    } finally {
      setLoading(false);
    }
  }, [adminKey, historyFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function approve(verificationId: number): Promise<void> {
    try {
      const result = await request<{ email_queued?: boolean }>(
        `/enrollment-verifications/${verificationId}/approve`,
        {
          method: "POST",
          headers: reviewerHeaders(adminKey),
          body: JSON.stringify({ valid_months: 12 }),
        }
      );
      setToast({
        kind: "ok",
        text: result.email_queued
          ? `Application #${verificationId} APPROVED — applicant is being emailed.`
          : `Application #${verificationId} APPROVED — email NOT sent (SMTP not configured).`,
      });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.code === "DECISION_ALREADY_MADE") {
        // Someone (or an earlier click) already decided; resync the queue.
        setToast({ kind: "warn", text: `Application #${verificationId} was already decided.` });
        await refresh();
        return;
      }
      setToast({ kind: "warn", text: err instanceof ApiError ? err.message : "Approval failed." });
    }
  }

  async function reject(verificationId: number, comment: string): Promise<void> {
    if (!comment.trim()) {
      setToast({ kind: "warn", text: "A rejection comment is required." });
      return;
    }
    try {
      const result = await request<{ email_queued?: boolean }>(
        `/enrollment-verifications/${verificationId}/reject`,
        {
          method: "POST",
          headers: reviewerHeaders(adminKey),
          body: JSON.stringify({ comment }),
        }
      );
      setToast({
        kind: "ok",
        text: result.email_queued
          ? `Application #${verificationId} REJECTED — applicant is being emailed.`
          : `Application #${verificationId} REJECTED — email NOT sent (SMTP not configured).`,
      });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.code === "DECISION_ALREADY_MADE") {
        setToast({ kind: "warn", text: `Application #${verificationId} was already decided.` });
        await refresh();
        return;
      }
      setToast({ kind: "warn", text: err instanceof ApiError ? err.message : "Rejection failed." });
    }
  }

  function corPdfUrl(verificationId: number): string {
    // Key travels in the query string: a plain browser tab cannot send
    // the X-Admin-Key header.
    return `${API}/enrollment-verifications/${verificationId}/cor?key=${encodeURIComponent(adminKey)}`;
  }

  return {
    adminKey,
    setAdminKey,
    queue,
    history,
    historyFilter,
    setHistoryFilter,
    loading,
    message,
    toast,
    approve,
    reject,
    refresh,
    corPdfUrl,
  };
}
