/**
 * useLogin — real session-cookie login (ADR-019).
 *
 * On success: stores the CSRF token in memory (apiClient) and returns the
 * authenticated user + expiry timestamps. The session credential itself
 * lives only in the HttpOnly cookie.
 */
import { useCallback, useState } from "react";
import { request, ApiError, setCsrfToken } from "../../services/apiClient";

export interface SessionUser {
  user_id: number;
  email: string;
  role_code: string;
  account_status: string;
  first_name: string;
  last_name: string;
}

export interface AuthResult {
  user: SessionUser;
  csrf_token: string;
  idle_expires_at: string;
  absolute_expires_at: string;
}

export interface LoginResult {
  ok: boolean;
  message: string;
  auth?: AuthResult;
}

export function useLogin() {
  const [submitting, setSubmitting] = useState(false);

  const login = useCallback(async (identifier: string, password: string): Promise<LoginResult> => {
    setSubmitting(true);
    try {
      const auth = await request<AuthResult>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });
      setCsrfToken(auth.csrf_token);
      return {
        ok: true,
        message: `Signed in as ${auth.user.first_name} ${auth.user.last_name}.`,
        auth,
      };
    } catch (err) {
      setCsrfToken(null);
      if (err instanceof ApiError) {
        return { ok: false, message: err.message };
      }
      return { ok: false, message: "Login failed." };
    } finally {
      setSubmitting(false);
    }
  }, []);

  return { login, submitting };
}
