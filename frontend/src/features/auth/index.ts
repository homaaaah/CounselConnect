/**
 * Feature module: auth (login/session UI, ADR-019).
 * Opaque HttpOnly session cookie + in-memory CSRF token.
 */
export { useLogin, type LoginResult, type AuthResult, type SessionUser } from "./useLogin";
export { useSession, type SessionState } from "./useSession";
