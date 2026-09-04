/**
 * Minimal API client (structural placeholder).
 *
 * Rules (NAMING_CONVENTIONS.md / docs/API_CONTRACT.md):
 * - Base URL from VITE_API_BASE_URL (ends with /api/v1).
 * - JSON fields travel as snake_case; do NOT convert case globally.
 * - Errors use the standard envelope: { "error": { code, message, details } }.
 *
 * TODO: Implement after authentication/session mechanism is approved
 * (ADR-P01) — auth headers/credentials handling depends on it.
 */

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface ApiErrorEnvelope {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(status: number, envelope: ApiErrorEnvelope) {
    super(envelope.error.message);
    this.code = envelope.error.code;
    this.status = status;
    this.details = envelope.error.details ?? {};
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    const envelope = (await response.json().catch(() => null)) as ApiErrorEnvelope | null;
    throw new ApiError(response.status, envelope ?? {
      error: { code: "NETWORK_ERROR", message: "Request failed." },
    });
  }
  return (await response.json()) as T;
}
