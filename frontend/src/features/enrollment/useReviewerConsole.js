/**
 * useReviewerConsole — counselor review of registration applications
 * (DFD 1.3). Views the pending queue with applicant details, previews the
 * COR PDF, approves, or rejects with a required comment.
 *
 * Auth (ADR-019): session cookie via `credentials: "include"` + CSRF
 * header; requires the COUNSELOR role server-side.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

const API = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export function useReviewerConsole() {
  const [queue, setQueue] = useState([]);
  const [history, setHistory] = useState([]);
  const [historyFilter, setHistoryFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [toast, setToast] = useState(null);
  const pdfBlobs = useRef({});
  const pdfGeneration = useRef({});
  const mounted = useRef(true);

  function discardPdf(verificationId) {
    pdfGeneration.current[verificationId] = (pdfGeneration.current[verificationId] ?? 0) + 1;
    const url = pdfBlobs.current[verificationId];
    if (url) URL.revokeObjectURL(url);
    delete pdfBlobs.current[verificationId];
  }

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      Object.values(pdfBlobs.current).forEach((url) => URL.revokeObjectURL(url));
      pdfBlobs.current = {};
    };
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8000);
    return () => clearTimeout(t);
  }, [toast]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [pending, all] = await Promise.all([
        request("/enrollment-verifications/pending"),
        request(
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

  async function approve(verificationId) {
    try {
      const result = await request(
        `/enrollment-verifications/${verificationId}/approve`,
        { method: "POST", body: JSON.stringify({ valid_months: 12 }) }
      );
      discardPdf(verificationId);
      setToast({
        kind: "ok",
        text: result.email_queued
          ? `Application #${verificationId} APPROVED — applicant is being emailed.`
          : `Application #${verificationId} APPROVED — email NOT sent (SMTP not configured).`,
      });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.code === "DECISION_ALREADY_MADE") {
        discardPdf(verificationId);
        setToast({ kind: "warn", text: `Application #${verificationId} was already decided.` });
        await refresh();
        return;
      }
      setToast({ kind: "warn", text: err instanceof ApiError ? err.message : "Approval failed." });
    }
  }

  async function reject(verificationId, comment) {
    if (!comment.trim()) {
      setToast({ kind: "warn", text: "A rejection comment is required." });
      return;
    }
    try {
      const result = await request(
        `/enrollment-verifications/${verificationId}/reject`,
        { method: "POST", body: JSON.stringify({ comment }) }
      );
      discardPdf(verificationId);
      setToast({
        kind: "ok",
        text: result.email_queued
          ? `Application #${verificationId} REJECTED — applicant is being emailed.`
          : `Application #${verificationId} REJECTED — email NOT sent (SMTP not configured).`,
      });
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.code === "DECISION_ALREADY_MADE") {
        discardPdf(verificationId);
        setToast({ kind: "warn", text: `Application #${verificationId} was already decided.` });
        await refresh();
        return;
      }
      setToast({ kind: "warn", text: err instanceof ApiError ? err.message : "Rejection failed." });
    }
  }

  async function openCorPdf(verificationId) {
    const generation = pdfGeneration.current[verificationId] ?? 0;
    if (pdfBlobs.current[verificationId]) {
      window.open(pdfBlobs.current[verificationId], "_blank");
      return;
    }
    try {
      // Fetch with cookies (a plain <a> tag cannot send credentials
      // cross-origin), then open the blob URL in a new tab.
      const res = await fetch(
        `${API}/enrollment-verifications/${verificationId}/cor`,
        { credentials: "include", cache: "no-store" }
      );
      if (!res.ok) throw new Error("fetch failed");
      const blob = await res.blob();
      if (!mounted.current || (pdfGeneration.current[verificationId] ?? 0) !== generation) return;
      const url = URL.createObjectURL(blob);
      discardPdf(verificationId);
      pdfBlobs.current[verificationId] = url;
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
