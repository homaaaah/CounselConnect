import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, request } from "../../services/apiClient";

/** Private appointment attachments shared by the assigned Student and Counselor. */
export function useSessionDocuments(appointmentId, enabled = true) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(enabled);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const path = `/appointments/${appointmentId}/documents`;

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      setDocuments(await request(path));
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [path, enabled]);
  useEffect(() => { void load(); }, [load]);

  const upload = useCallback(async file => {
    if (!file) return false;
    setBusy(true);
    const data = new FormData();
    data.append("file", file);
    try {
      const uploaded = await request(path, { method: "POST", body: data });
      setDocuments(current => [uploaded, ...current]);
      setError("");
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }, [path]);

  const remove = useCallback(async documentId => {
    setBusy(true);
    try {
      await request(`${path}/${documentId}`, { method: "DELETE" });
      setDocuments(current => current.filter(item => item.document_id !== documentId));
      setError("");
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setBusy(false);
    }
  }, [path]);

  const download = useCallback(async doc => {
    try {
      const response = await fetch(`${API_BASE_URL}${path}/${doc.document_id}/download`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error("The file could not be downloaded.");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.original_filename;
      link.click();
      URL.revokeObjectURL(url);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [path]);

  return { documents, loading, busy, error, upload, remove, download, reload: load };
}
