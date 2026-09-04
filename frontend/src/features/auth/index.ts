/**
 * Feature module: auth (login/session UI).
 * Session mechanism pending ADR-P01 — the backend returns a structured
 * AUTH_MECHANISM_PENDING response; the UI shows it instead of faking login.
 */
export { useLogin, type LoginResult } from "./useLogin";
