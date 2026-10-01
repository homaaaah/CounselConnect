# CounselConnect - Current Task

**Status:** COMPLETED
**Task:** Registration UI QoL — polish + editable/read-only affordances + remove "Re-upload COR" from the confirm step (plan `.kilo/plans/registration-ui-qol.md`).

## Objective

Polish the registration/verification UI: grouped button layout, per-phase heading/copy, a clear legend and per-field lock/pencil chip showing editable vs read-only, and a simpler review step. On `AWAITING_CONFIRMATION`, the confirm step offers Confirm/Edit + Reject account but **no** Re-upload COR; Re-upload COR remains only for `NEEDS_RESUBMISSION`/`FAILED` via the upload form.

## In scope

- `frontend/src/index.css`: `.form-actions`, `.btn-submit.btn-secondary`, `.btn-submit.btn-danger`, `.field-legend`, `.field-chip` (+ `--locked`/`--editable`), `.input-locked`.
- `frontend/src/features/accounts/ScreeningFields.jsx`: legend + per-field lock/pencil chip; locked inputs use `.input-locked`; chips on select labels (campus/program/year level).
- `frontend/src/pages/RegisterPage.jsx`: remove confirm-step Re-upload COR (and `handleReRequest`); per-phase heading/subtitle; `.form-actions` + danger class (no inline styles).
- `frontend/src/pages/student/RegistrationStatusPage.jsx`: remove confirm-form Re-upload COR and `wantResubmit`/`handleReRequest`; status-based heading; `.form-actions`.
- Tests: `cor-screening.test.cjs`, `registration.test.cjs`, `session.test.cjs` (heading expectation).
- Docs wording: ADR-033, REGISTRATION_VERIFICATION.

## Out of scope

- Backend/API/status changes (none).
- Re-upload behavior for `NEEDS_RESUBMISSION`/`FAILED` (unchanged).
- Aligning modal vs `#registration` beyond shared components (not a separate deliverable).

## Acceptance criteria

1. On `AWAITING_CONFIRMATION`, neither confirm surface shows Re-upload COR.
2. Re-upload is still reachable for `NEEDS_RESUBMISSION`/`FAILED`/no-COR via the upload form.
3. Buttons grouped/spaced; destructive action uses `.btn-danger` (no inline styles).
4. Heading + subtitle reflect the phase/status.
5. Every field shows a legend + Read-only (lock) or Editable (pencil) chip; locked inputs styled distinctly.
6. `npm run build` passes; `npm test` passes except the 3 pre-existing calendar failures.

## Verification

- `npm test` -> **73 passed, 3 failed** (the 3 pre-existing `appointments.test.cjs` calendar date-rot).
- `npm run build` -> succeeded.
- No backend change; no OpenAPI/migration change.

## Notes

- The confirm step now has no `handleReRequest`/`wantResubmit`; the upload form is the single re-upload path.
- `window.confirm` guard for Reject account unchanged.

## Unresolved human decisions

- None blocking.
