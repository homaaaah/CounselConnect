/**
 * useSession — current-session state (ADR-019).
 *
 * `restore` revalidates the cookie via GET /auth/me (safe), then recovers
 * the CSRF token via GET /auth/csrf after a page reload (the token lives
 * in memory only). `logout` revokes the session server-side.
 */
import { useCallback, useState } from "react";
import { request, setCsrfToken } from "../../services/apiClient";
import type { SessionUser, AuthResult } from "./useLogin";

export interface SessionState {
  user: SessionUser | null;
  idleExpiresAt: string | null;
  absoluteExpiresAt: string | null;
  ready: boolean; // first /auth/me check finished
}

export function useSession() {
  const [state, setState] = useState<SessionState>({
    user: null,
    idleExpiresAt: null,
    absoluteExpiresAt: null,
    ready: false,
  });

  const restore = useCallback(async () => {
    try {
      const user = await request<SessionUser>("/auth/me");
      // Recover the CSRF token after a reload (safe GET, re-issues it).
      let idle: string | null = null;
      let absolute: string | null = null;
      try {
        const auth = await request<AuthResult>("/auth/csrf");
        setCsrfToken(auth.csrf_token);
        idle = auth.idle_expires_at;
        absolute = auth.absolute_expires_at;
      } catch {
        setCsrfToken(null); // safe-method-only browsing until re-login
      }
      setState({ user, idleExpiresAt: idle, absoluteExpiresAt: absolute, ready: true });
    } catch {
      setCsrfToken(null);
      setState({ user: null, idleExpiresAt: null, absoluteExpiresAt: null, ready: true });
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await request<void>("/auth/logout", { method: "POST", body: "{}" });
    } catch {
      // Session already gone server-side; clear locally regardless.
    }
    setCsrfToken(null);
    setState({ user: null, idleExpiresAt: null, absoluteExpiresAt: null, ready: true });
  }, []);

  return { ...state, restore, logout };
}
