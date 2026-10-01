# Plan: Registration UI QoL — polish + remove "Re-upload COR" from the confirm step

**Status:** implementation-ready
**Risk:** MEDIUM (frontend presentation + controls; no backend/API/data change)
**Implement with:** an implementation-capable agent.

## Goal

1. Fix the registration UI: button layout/visual polish, per-phase heading/copy, clearer locked-vs-editable fields, and a simpler review step.
2. In the **Confirm details** step, when the screening is `AWAITING_CONFIRMATION`, **remove the "Re-upload COR" option**.

## Decisions

- **Remove "Re-upload COR" from the confirm-details form on both surfaces** (`RegisterPage` modal and `RegistrationStatusPage`). It is redundant/incorrect there: `AWAITING_CONFIRMATION` should only Confirm/Edit, and `NEEDS_RESUBMISSION`/`FAILED` already render the dedicated upload form below. Re-upload remains available via the upload form only.
- Keep **Reject account** available on the review and re-upload steps (unchanged).
- Introduce reusable CSS classes instead of inline styles: `.form-actions`, `.btn-submit.btn-secondary`, `.btn-submit.btn-danger`.
- Presentation-only; no API, screening status, or contract behavior changes.

## Changes

### A. CSS (`frontend/src/index.css`, auth-card section)
- Add `.form-actions` (a flex column with `gap`, `margin-top`) to group the actions on the confirm/resubmit steps.
- Add `.btn-submit.btn-secondary` (neutral outline: transparent/white background, border) and `.btn-submit.btn-danger` (red text + border; hover tint) mirroring the existing `.btn-success` pattern.
- Add explicit editable/locked field styling and a per-field chip:
  - `.field-chip` (tiny inline label next to the field label) with `.field-chip--locked` (grey) and `.field-chip--editable` (primary/blue).
  - `.field-legend` (intro line above the fields) and `.input-locked` (greyed background, dashed/soft border, `cursor: not-allowed`).

### B. Confirm step — remove duplicate "Re-upload COR"
- `RegisterPage.jsx` confirm phase: delete the `Re-upload COR` button; keep primary (Confirm / Submit edit request) and **Reject account**.
- Remove the now-unused `handleReRequest`.
- `RegistrationStatusPage.jsx`: delete the confirm-form `Re-upload COR` button and remove the `wantResubmit` state + `handleReRequest`; the existing `canResubmit` upload form already covers re-upload and still shows for `NEEDS_RESUBMISSION`/`FAILED`/no screening.

### C. Per-phase heading + subtitle
- `RegisterPage.jsx` header: make the `<h1>` and `<p>` depend on `phase`:
  - `form`: "Create your account" + current text (email/password/COR).
  - `confirm`: "Review your details" + "Check what we read from your COR. Confirm to activate, or request an edit for Superadmin approval."
  - `resubmit`: "Re-upload your COR" + "We could not read your COR clearly. Upload a clearer or corrected PDF."
  - `done`: "You're all set" + keep the activation/pending-edit message.
  - `cancelled`: "Registration cancelled" + keep the deletion message.
- `RegistrationStatusPage.jsx` intro copy: choose by status (`AWAITING_CONFIRMATION` -> review; `NEEDS_RESUBMISSION`/`FAILED`/none -> re-upload), instead of one static sentence.

### D. Make editable vs non-editable fields explicitly visible
`ScreeningFields.jsx` is the single shared component (do not fork). Every field must make its editability obvious:
- **Per-field chip/label** next to each field label, using FontAwesome icons already loaded in the app:
  - Locked (non-editable): `<i class="fa-solid fa-lock">` + chip text `Read-only` (locked styling `.input-locked`, greyed background, `cursor: not-allowed`).
  - Editable: `<i class="fa-solid fa-pen">` + chip text `Editable` (`.field-chip--editable`, normal white input).
- **Legend** (`.field-legend`) above the fields:
  - `editable=true`: "Fields with a 🔒 lock were read from your COR and cannot be changed; fields with a ✎ pencil you can edit (changes are reviewed)."
  - `editable=false` (view-only, e.g. non-confirmable `#registration`): "These details were read from your COR and cannot be changed here."
- `Locked` keeps `readOnly` + `aria-readonly="true"`; add `aria-describedby` linking the hint, and keep the chip `aria-hidden` with the same meaning conveyed in the hint text for screen readers.
- Keep the existing ids (`confirm-*`) so tests and analytics stay stable.
- The chip must reflect the true state: `student_number`, `academic_period`, and a COR-**matched** `campus`/`program` are locked; names, `year_level`, `section`, and an **unmatched** campus/program selection are editable in `editable` mode.
- In the confirm step, show the edit note only when `hasEdits` (already) and drop the redundant secondary hint lines.

### E. Simplify the review step
- Wrap the actions in `.form-actions`: primary action first, then optional **Reject account** (danger). Remove the extra `!confirmable` hint where the status message already explains it (keep one concise hint).

## Files
- `frontend/src/index.css`
- `frontend/src/pages/RegisterPage.jsx`
- `frontend/src/pages/student/RegistrationStatusPage.jsx`
- `frontend/src/features/accounts/ScreeningFields.jsx`
- Tests: `frontend/tests/cor-screening.test.cjs`, `frontend/tests/registration.test.cjs`

## Docs
The flow docs currently say the two choices appear on "the review and re-upload steps" (ADR-033 / `REGISTRATION_VERIFICATION.md` / `API_CONTRACT.md` / `SECURITY.md`). Update the wording to: **Reject account** is offered on the review and re-upload steps; **Re-upload COR** is offered only when the screening needs resubmission (the re-upload step). No behavior/API change.
- `.ai/DECISIONS.md` (ADR-033 wording), `docs/REGISTRATION_VERIFICATION.md`, `docs/API_CONTRACT.md`, `docs/SECURITY.md`, `.ai/CURRENT_TASK.md`.

## Tests
- `frontend/tests/cor-screening.test.cjs`:
  - Replace "re-upload COR opens the upload form without calling reject" with: on `AWAITING_CONFIRMATION`, the confirm step has **no** "Re-upload COR" control (and Confirm + Reject account are present); a `NEEDS_RESUBMISSION` screening still shows the upload form (and no `/reject` call).
  - Keep the reject-account and profile-edit tests (unaffected).
- `frontend/tests/registration.test.cjs`:
  - Assert the modal confirm step has no "Re-upload COR" and still confirms/edit-requests/rejects.
  - Assert the editability affordances: `student_number`/`academic_period` render the "Read-only" chip (and `readOnly`), an editable field (e.g. `confirm-last-name`) renders the "Editable" chip, and a COR-matched `campus` renders as read-only.
  - Keep the technical-failure and modal reject-account tests.
- Run `npm test` (expect only the 3 pre-existing calendar failures) and `npm run build`.
- No backend change, so no backend/OpenAPI rerun required (but a quick `pytest` sanity run is optional).

## Risks / notes
- Removing a control is user-visible: ensure `NEEDS_RESUBMISSION`/`FAILED` still expose the upload form (modal resubmit phase and `#registration` `canResubmit`), so re-upload is never lost.
- Smooth `window.confirm` guard stays as-is for reject-account.
- MEDIUM risk per the workflow: one read-only in-task review against these acceptance criteria after implementation.

## Acceptance criteria
1. On `AWAITING_CONFIRMATION`, neither the modal confirm step nor the `#registration` confirm form shows "Re-upload COR".
2. Re-upload is still reachable for `NEEDS_RESUBMISSION`/`FAILED` (and no-COR) via the upload form.
3. Buttons are grouped/spaced consistently; the destructive action uses a danger style (no inline styles).
4. Heading + subtitle reflect the current phase/status.
5. Every confirm/review field visibly shows whether it is editable or read-only: a legend plus a per-field lock/pencil chip/icon, with locked inputs styled distinctly; the distinction is exposed to screen readers.
6. Frontend build passes and tests pass except the 3 pre-existing calendar failures.

## Ordered tasks
1. Add `.form-actions`, `.btn-submit.btn-secondary`, `.btn-submit.btn-danger` to `index.css`.
2. Remove "Re-upload COR" from both confirm forms; delete the now-dead `handleReRequest`/`wantResubmit`.
3. Per-phase heading/subtitle in `RegisterPage`; status-based intro in `RegistrationStatusPage`.
4. `ScreeningFields`: legend + per-field lock/pencil chip/icon, locked styling, `aria` wiring; concise hints.
5. Group actions and simplify the review step.
6. Update frontend tests; run `npm test` + `npm run build`.
7. Doc wording updates (ADR-033, REGISTRATION_VERIFICATION, API_CONTRACT, SECURITY, CURRENT_TASK).
8. Read-only in-task review against the acceptance criteria.