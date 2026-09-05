/**
 * useReviewerConsole — counselor review of registration applications
 * (DFD 1.3). Views the pending queue with applicant details, previews the
 * COR PDF, approves, or rejects with a required comment.
 *
 * Auth (ADR-019): session cookie via `credentials: "include"` + CSRF
 * header; requires the COUNSELOR role server-side.
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

export function useReviewerConsole() {
  const [queue, setQueue] = useState<PendingApplication[]>([]);
  const [history, setHistory] = useState<PendingApplication[]>([]);
  const [historyFilter, setHistoryFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "warn"; text: string } | null>(null);
  const [pdfBlobs, setPdfBlobs] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(t);
  }, [toast]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [pending, all] = await Promise.all([
        request<PendingApplication[]>("/enrollment-verifications/pending"),
        request<PendingApplication[]>(
          historyFilter
            ? `/enrollment-verifications/history?status=${historyFilter}`
            : "/enrollment-verifications/history"
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
  }, [historyFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function approve(verificationId: number): Promise<void> {
    try {
      const result = await request<{ email_queued?: boolean }>(
        `/enrollment-verifications/${verificationId}/approve`,
        { method: "POST", body: JSON.stringify({ valid_months: 12 }) }
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
        { method: "POST", body: JSON.stringify({ comment }) }
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

  async function openCorPdf(verificationId: number): Promise<void> {
    if (pdfBlobs[verificationId]) {
      window.open(pdfBlobs[verificationId], "_blank");
      return;
    }
    try {
      // Fetch with cookies (a plain <a> tag cannot send credentials
      // cross-origin), then open the blob URL in a new tab.
      const res = await fetch(
        `${API}/enrollment-verifications/${verificationId}/cor`,
        { credentials: "include" }
      );
      if (!res.ok) throw new Error("fetch failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setPdfBlobs((prev) => ({ ...prev, [verificationId]: url }));
      window.open(url, "_blank");
    } catch {
      setToast({ kind: "warn", text: `Could not open the COR PDF for #${verificationId}.` });
    }
  }

  return {
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
    openCorPdf,
  };
}
