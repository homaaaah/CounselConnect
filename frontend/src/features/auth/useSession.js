/**
 * useSession — current-session state (ADR-019).
 *
 * Restore user and CSRF together before mounting protected pages.
 * Credentials remain in HttpOnly cookies; CSRF stays in memory.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, request, setCsrfToken, setSessionActivityHandler, setUnauthorizedHandler } from "../../services/apiClient";

export function useSession() {
  const [state, setState] = useState({
    user: null,
    idleExpiresAt: null,
    absoluteExpiresAt: null,
    ready: false, // user and CSRF restoration finished
    error: null,
  });
  const generation = useRef(0);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      generation.current++;
      setState({ user: null, idleExpiresAt: null, absoluteExpiresAt: null, ready: true, error: null });
    });
    setSessionActivityHandler(() => {
      setState(previous => {
        if (!previous.user || !previous.absoluteExpiresAt) return previous;
        const idle = Math.min(
          Date.now() + 60 * 60_000,
          new Date(previous.absoluteExpiresAt).getTime(),
        );
        return { ...previous, idleExpiresAt: new Date(idle).toISOString() };
      });
    });
    return () => {
      setUnauthorizedHandler(null);
      setSessionActivityHandler(null);
    };
  }, []);

  const accept = useCallback((auth) => {
    generation.current++;
    setCsrfToken(auth.csrf_token);
    setState({ user: auth.user, idleExpiresAt: auth.idle_expires_at,
      absoluteExpiresAt: auth.absolute_expires_at, ready: true, error: null });
  }, []);

  const restore = useCallback(async () => {
    const current = ++generation.current;
    setState((previous) => ({ ...previous, ready: false, error: null }));
    try {
      const auth = await request("/auth/csrf");
      if (generation.current !== current) return;
      accept(auth);
    } catch (err) {
      if (generation.current !== current) return;
      setCsrfToken(null);
      setState({ user: null, idleExpiresAt: null, absoluteExpiresAt: null, ready: true,
        error: err instanceof ApiError && err.status === 401 ? null : "Could not restore your session. Please sign in again." });
    }
  }, [accept]);

  const logout = useCallback(async () => {
    generation.current++;
    try {
      await request("/auth/logout", { method: "POST", body: "{}" });
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        setState((previous) => ({ ...previous, error: "Sign out failed. Please retry." }));
        return false;
      }
    }
    setCsrfToken(null);
    setState({ user: null, idleExpiresAt: null, absoluteExpiresAt: null, ready: true, error: null });
    return true;
  }, []);

  const continueSession = useCallback(async () => {
    const auth = await request("/auth/refresh", { method: "POST", body: "{}" });
    accept(auth);
    return true;
  }, [accept]);

  return { ...state, accept, restore, logout, continueSession };
}
