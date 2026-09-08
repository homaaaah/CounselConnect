# CounselConnect — Current Task

**Status:** COMPLETED — appointment scheduling; Live Chat integration remains separate.
**Risk class:** HIGH (authorization, appointment reservations, concurrent transitions)

## Objective

Implement appointment scheduling from Flowchart V1 page 4 using the existing React/FastAPI/MySQL modular monolith.

## Delivered

- Counselor-owned concrete availability from campus/time range/duration/mode, with cross-campus overlap checks and Counselor-only Guidance Office location updates.
- Active Student slot search and pending requests; assigned Counselor confirmation/rejection and outcomes; owner/assigned-Counselor cancellation and rescheduling back to pending review.
- Atomic participant/appointment/slot locking; double-booking and overlapping Student appointment protection; failed replacement preservation; slot release and minimal transactional audit events.
- Mode compatibility and face-to-face location snapshots, revalidated on replacement. All API timestamps use UTC; UI input/display uses Asia/Manila.
- Authenticated `#appointments` navigation, student home link, counselor controls, filters/pagination, loading/empty/error/conflict states, and CSRF-protected mutations.
- Existing linked appointment conversations are validated and closed on terminal outcomes through the messaging service. New chat creation/joining/exchange remains unimplemented and is disclosed in the UI.
- Scheduling/API contracts and generated OpenAPI updated. Existing student/staff login-form changes are preserved.

## Verification (2026-09-08)

- Backend: **117 passed**, no skips, against a unique disposable MySQL schema. Includes all state/action combinations, concurrent same-slot and overlapping-Student requests, simultaneous confirmation/rejection, ownership/role/active-account/CSRF checks, UTC output, snapshots, rollback, linked-chat closure validation, and existing registration/security regressions.
- A real React-to-FastAPI/MySQL test creates availability, books, confirms, reschedules, reconfirms, and cancels through the actual appointment forms. Test campus filtering prevents interference from other synthetic fixtures in the shared disposable schema.
- Frontend: **16 passed**; TypeScript/Vite production build passed.
- Focused Ruff checks, OpenAPI drift check, and git diff whitespace checks passed.
- Two existing dependency deprecation warnings remain. Component/HTTP integration is not a full browser/device test.
- The existing local backend was restarted on port 8000 to load the new endpoints. No migration or production deployment was performed.

## Remaining scope

- Live Chat transport/joining/message exchange and its complete lifecycle remain separate under the messaging contract.
- Slot duration/buffer policy, cancellation/reschedule cutoff, blocked periods, reminders, detailed no-show threshold, and any pre-start join allowance remain pending decisions. No additional policies or meeting-platform integration were invented.
- Scheduling supports explicit refresh; it does not introduce background polling.
