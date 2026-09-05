/**
 * API client (ADR-019 session-cookie auth).
 *
 * - Base URL from VITE_API_BASE_URL (ends with /api/v1).
 * - Session credential travels in the HttpOnly `counselconnect_session`
 *   cookie (never in JS); `credentials: "include"` sends it.
 * - CSRF: login/refresh return `csrf_token`; unsafe methods must echo it
 *   in the X-CSRF-Token header (stored in memory only — NOT localStorage).
 * - JSON fields travel as snake_case; do NOT convert case globally.
 * - Errors use the standard envelope: { "error": { code, message, details } }.
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

/** In-memory CSRF token (survives navigation, cleared on reload/logout). */
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  const method = (init.method ?? "GET").toUpperCase();
  // Attach when present; the SERVER enforces CSRF on unsafe methods for
  // authenticated endpoints. Public POSTs (login/register) have no token
  // yet, and CSRF does not apply to them (no ambient cookie to forge).
  if (UNSAFE_METHODS.has(method) && csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const envelope = (await response.json().catch(() => null)) as ApiErrorEnvelope | null;
    if (response.status === 401) {
      setCsrfToken(null); // session gone/invalid — force re-login
    }
    throw new ApiError(response.status, envelope ?? {
      error: { code: "NETWORK_ERROR", message: "Request failed." },
    });
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
