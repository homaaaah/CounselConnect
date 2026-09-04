/**
 * useLogin — submits credentials to POST /auth/login.
 *
 * Until ADR-P01 is approved, the backend answers with a structured
 * AUTH_MECHANISM_PENDING error; this hook surfaces that honestly.
 */
import { useState } from "react";
import { request, ApiError } from "../../services/apiClient";

export interface LoginResult {
  pending: boolean;
  message: string;
}

export function useLogin() {
  const [submitting, setSubmitting] = useState(false);

  async function login(identifier: string, password: string): Promise<LoginResult> {
    setSubmitting(true);
    try {
      // A successful response is impossible until ADR-P01; typed as never.
      await request<never>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });
      return { pending: false, message: "Logged in." };
    } catch (err) {
      if (err instanceof ApiError && err.code === "AUTH_MECHANISM_PENDING") {
        return {
          pending: true,
          message:
            "Sign-in is not available yet. The team still needs to approve the authentication mechanism (ADR-P01).",
        };
      }
      return {
        pending: false,
        message: err instanceof Error ? err.message : "Login failed.",
      };
    } finally {
      setSubmitting(false);
    }
  }

  return { login, submitting };
}
