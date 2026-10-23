# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Implement appointment-bound WebRTC calls (Student + assigned Counselor) per `.kilo/plans/1792774405483-video-demo-test-button.md`.
**Route:** `appointments` + `messaging` + `security`; HIGH risk (authorization, signaling, privacy).

## Result

The owning Student and assigned Counselor of a `CONFIRMED` `ONLINE` appointment can join a one-to-one call from `ScheduledSessionPage` between the scheduled start and appointment end plus the existing 15-minute grace. The backend authenticates the session/Origin, authorizes participant/status/mode/time on connect and revalidates every 30 seconds by wall clock, and relays SDP/ICE only between the two participants over a dedicated appointment WebSocket. Media is peer-to-peer; no media, SDP, ICE candidates, IP addresses, call history, or audit events are persisted or logged. The call is independent of chat join and never changes the appointment outcome. The manual `#video-demo` prototype and its Home shortcuts were retired.

## Files changed

### New

- `backend/app/modules/calls/{__init__,schemas,service,realtime,router}.py`
- `backend/app/shared/realtime.py`
- `backend/app/tests/integration/test_calls.py` (18 DB-backed tests)
- `frontend/src/features/calls/{index.js,signaling.js,useAppointmentCall.js}`
- `frontend/src/components/calls/AppointmentCallPanel.jsx`
- `frontend/src/services/realtime.js`
- `frontend/tests/appointment-call.test.cjs` (10 tests)

### Modified

- `backend/app/config.py` — `CallIceServerConfig`, `call_ice_servers`, signal size/rate limits.
- `backend/app/modules/appointments/{service,schemas}.py` — `CallContext`, `call_context`, shared `_live_window`, `can_call` capability.
- `backend/app/modules_router.py` — mount the calls router.
- `backend/app/modules/messaging/realtime.py` — use the shared socket auth helper.
- `backend/.env.example` — call ICE/signal settings.
- `contracts/openapi.json` — regenerated.
- `frontend/src/pages/ScheduledSessionPage.jsx` — call panel; prototype link removed.
- `frontend/src/features/messaging/{index.js,useAppointmentChat.js,useScheduledSessions.js}` — `socketUrl` moved to `services/realtime.js`.
- `frontend/tests/scheduled-chat.test.cjs` — `can_call` fixtures and call-panel test.
- `docs/AUDIO_VIDEO_CALLS.md`, `docs/API_CONTRACT.md`, `docs/APPOINTMENT_SCHEDULING.md`, `docs/REAL_TIME_MESSAGING.md`.
- `.ai/{ARCHITECTURE,CONTEXT_MAP,DECISIONS,CURRENT_TASK}.md` — ADR-034 and routing map.
- Removed: `frontend/src/features/video/*`, `frontend/src/pages/VideoCallPrototypePage.jsx`, `frontend/tests/video-prototype.test.cjs`, plus `#video-demo` route/Home shortcut references (these files were untracked, so removal restores the prior tree).

## Verification

- `backend` calls tests with the disposable MySQL test DB: **23 passed, 0 failed**.
- Full backend suite with the test DB: **256 passed, 1 failed** — the pre-existing `test_live_appointment_screens` harness failure (`StudentHomePage` useToast outside `ToastProvider` in `frontend/tests/live-appointments.cjs`); unrelated to this change and untouched.
- `python scripts/export_openapi.py --check`: **matches the application**.
- `frontend` full suite: **85 passed, 2 failed** — only the two pre-existing calendar date-rot tests (`2026-09-19` past fixture and the UTC/Manila window drift).
- `npm run build`: **succeeded** (79 modules).
- `git diff --check`: no whitespace errors; line-ending warnings only.
- Independent read-only HIGH-risk review completed. Confirmed findings were fixed: wall-clock periodic revalidation (busy-client case), duplicate-connection takeover ends both sides, stale async offers discarded after hang-up, non-callable appointment copy, dead-peer cleanup, added regression tests, and contract/config wording.

## Not run

- Interactive two-browser manual call, real camera-indicator, real TURN/STUN network behavior, and Capacitor. These require devices/browsers and remain for human verification.

## Remaining limitations

- TURN uses static environment credentials in v1; ephemeral coturn credentials and multi-process signaling are follow-ups.
- One backend process only (the room registry is in memory, like chat).
- Both participants must explicitly join; there is no ringing/notification, and both must rejoin after a drop.
- P2P candidates can expose network addresses to the other authorized participant; documented in the UI/docs.
- The two calendar test failures and the live-appointments harness failure above remain pre-existing and were not modified.
