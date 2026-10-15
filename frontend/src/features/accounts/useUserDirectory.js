/**
 * useUserDirectory — Counselor read-only student directory (ADR-029).
 *
 * list: GET /accounts/students?page&page_size&q&screening_status
 * Also loads campus/program reference data once so rows can show names.
 * Backend authorization is authoritative (COUNSELOR only).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { request, ApiError } from "../../services/apiClient";

const PAGE_SIZE = 20;

function directoryQuery({ page, pageSize, query, status }) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (query) params.set("q", query);
  if (status) params.set("screening_status", status);
  return `/accounts/students?${params.toString()}`;
}

export function useUserDirectory() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [campuses, setCampuses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const seq = useRef(0);

  useEffect(() => {
    let active = true;
    Promise.allSettled([request("/accounts/campuses"), request("/accounts/programs")]).then(
      ([campusResult, programResult]) => {
        if (!active) return;
        if (campusResult.status === "fulfilled") setCampuses(campusResult.value?.items ?? []);
        if (programResult.status === "fulfilled") setPrograms(programResult.value?.items ?? []);
      },
    );
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const current = ++seq.current;
    setLoading(true);
    setError("");
    request(directoryQuery({ page, pageSize: PAGE_SIZE, query, status }))
      .then((data) => {
        if (current !== seq.current) return;
        setItems(data?.items ?? []);
        setTotal(data?.total ?? 0);
      })
      .catch((err) => {
        if (current !== seq.current) return;
        setError(err instanceof ApiError ? err.message : "Could not load users. Please retry.");
      })
      .finally(() => {
        if (current === seq.current) setLoading(false);
      });
    return () => {
      seq.current++;
    };
  }, [page, query, status, reloadKey]);

  const campusName = useCallback(
    (id) => campuses.find((c) => c.campus_id === id)?.campus_name ?? (id ? `#${id}` : "—"),
    [campuses],
  );
  const programName = useCallback(
    (id) => programs.find((p) => p.program_id === id)?.program_name ?? (id ? `#${id}` : "—"),
    [programs],
  );

  return {
    items,
    total,
    page,
    pageSize: PAGE_SIZE,
    pageCount: Math.max(1, Math.ceil(total / PAGE_SIZE)),
    query,
    status,
    loading,
    error,
    campusName,
    programName,
    search: (value) => {
      setPage(1);
      setQuery((value ?? "").trim());
    },
    filterStatus: (value) => {
      setPage(1);
      setStatus(value ?? "");
    },
    setPage,
    retry: () => setReloadKey((key) => key + 1),
  };
}

/** Lightweight total for the Counselor dashboard "Total users" card. */
export function useStudentCount() {
  const [total, setTotal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    request("/accounts/students?page=1&page_size=1")
      .then((data) => {
        if (active) setTotal(data?.total ?? 0);
      })
      .catch(() => {
        if (active) setError("Could not load users.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return { total, loading, error };
}
