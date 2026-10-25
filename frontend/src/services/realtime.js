/**
 * Real-time transport URL helpers.
 *
 * WebSocket routes authenticate with the same HttpOnly session cookie as REST
 * and require an allowlisted Origin on the server. Never add credentials to
 * the URL.
 */
import { API_BASE_URL } from "./apiClient";

export function socketUrl(path) {
  if (typeof window === "undefined" || !window.location?.origin) return null;
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
