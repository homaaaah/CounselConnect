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

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL?.trim() || "/api/v1").replace(/\/+$/, "");

/**
 * Coerce any error body to the standard envelope shape.
 * Handles: standard envelopes (pass through), non-envelope JSON (FastAPI
 * `detail` strings, gateway errors), and unparseable/empty bodies.
 */
function normalizeErrorBody(body) {
  if (body && typeof body === "object" && body.error
    && typeof body.error.message === "string") {
    return {
      error: {
        code: typeof body.error.code === "string" ? body.error.code : "REQUEST_FAILED",
        message: body.error.message,
        details: body.error.details ?? {},
      },
    };
  }
  const detail = body && typeof body === "object" && typeof body.detail === "string"
    ? body.detail : "Request failed.";
  return { error: { code: "REQUEST_FAILED", message: detail, details: {} } };
}

export class ApiError extends Error {
  constructor(status, envelope) {
    const normalized = normalizeErrorBody(envelope);
    super(normalized.error.message);
    this.code = normalized.error.code;
    this.status = status;
    this.details = normalized.error.details;
  }
}

/** In-memory CSRF token (survives navigation, cleared on reload/logout). */
let csrfToken = null;

export function setCsrfToken(token) {
  csrfToken = token;
}

export function getCsrfToken() {
  return csrfToken;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export async function request(path, init = {}) {
  const sentCsrfToken = csrfToken;
  const isFormData = init.body instanceof FormData;
  const headers = { ...init.headers };
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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const envelope = await response.json().catch(() => null);
    if (response.status === 401 && csrfToken === sentCsrfToken) {
      setCsrfToken(null); // session gone/invalid — force re-login
    }
    throw new ApiError(response.status, envelope ?? {
      error: { code: "NETWORK_ERROR", message: "Request failed." },
    });
  }
  if (response.status === 204) {
    return undefined;
  }
  return await response.json();
}
