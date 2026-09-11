/**
 * useLogin — real session-cookie login (ADR-019).
 *
 * On success: stores the CSRF token in memory (apiClient) and returns the
 * authenticated user + expiry timestamps. The session credential itself
 * lives only in the HttpOnly cookie.
 */
import { useCallback, useState } from "react";
import { request, ApiError, setCsrfToken } from "../../services/apiClient";

export function useLogin() {
  const [submitting, setSubmitting] = useState(false);

  const login = useCallback(async (identifier, password) => {
    setSubmitting(true);
    try {
      const auth = await request("/auth/login", {
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
