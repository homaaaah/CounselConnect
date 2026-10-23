/**
 * useLogin — real session-cookie login (ADR-019).
 *
 * On success: stores the CSRF token in memory (apiClient) and returns the
 * authenticated user + expiry timestamps. The session credential itself
 * lives only in the HttpOnly cookie.
 *
 * Audience gate: the Student form accepts only STUDENT accounts and the
 * Guidance form accepts only staff roles. A mismatched sign-in revokes the
 * session it just created instead of letting the wrong role through. The
 * rejection message is deliberately generic so it never reveals which
 * account type the credentials belong to.
 */
import { useCallback, useState } from "react";
import { request, ApiError, setCsrfToken } from "../../services/apiClient";

const STAFF_ROLES = ["COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN"];

const roleMatchesAudience = (role, audience) =>
  audience === "student" ? role === "STUDENT" : STAFF_ROLES.includes(role);

export function useLogin() {
  const [submitting, setSubmitting] = useState(false);

  const login = useCallback(async (identifier, password, audience = "student") => {
    setSubmitting(true);
    try {
      const auth = await request("/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });
      setCsrfToken(auth.csrf_token);
      if (!roleMatchesAudience(auth.user.role_code, audience)) {
        // Wrong form for this account: drop the fresh session so the wrong
        // role never becomes active, and tell the user which form to use.
        try {
          await request("/auth/logout", { method: "POST", body: "{}" });
        } catch {
          /* best effort; the session is replaced on the next successful login */
        }
        setCsrfToken(null);
        return {
          ok: false,
          message: "Incorrect identifier or password.",
        };
      }
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
