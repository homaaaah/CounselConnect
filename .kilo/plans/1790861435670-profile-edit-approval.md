# Plan: Student "Request Edit" during verification, approved by Superadmin

**Plan file:** `.kilo/plans/1790861435670-profile-edit-approval.md`
**Status:** implementation-ready
**Risk:** HIGH (role boundary + new approval workflow; ADR-030 amendment required)
**Implement with:** an implementation-capable agent (this plan contains no code changes).

## Goal

During registration verification (when the Student reviews the OCR-extracted fields), let the Student **request edits** to a limited set of their own information. Submitting the request **activates the account immediately** (using the COR-verified values already shown). The requested changes are stored as a **pending change request** and only take effect after a **Superadmin** approves them.

## Locked decisions

1. **Approver = `SUPERADMIN`** (user's explicit choice).
2. **Activation is decoupled from approval:** submitting the edit request activates the account using the COR-verified values; the requested values stay pending. Superadmin approves the *change*, not the registration.
3. **Editable fields (request-only):** `first_name`, `middle_name`, `last_name`, `year_level`, `section`.
4. **Never editable:** `student_number`, `academic_period` (academic year), `campus_id`, `program_id`.
5. **Review surface:** extend `frontend/src/pages/counselor/CounselorUsersPage.jsx` (`#users`) with a Superadmin-only pending queue + Approve/Reject (old→new diff).
6. **One pending request per Student.** A second submission is rejected (`409`). After a rejection the Student may submit a new request.
7. **Entry points:** both the in-modal confirm step (`X-COR-Token`) and the signed-in `#registration` fallback page.
8. **No student notification in v1** (user decision): on approve/reject, do nothing beyond persisting the decision + audit. No email, no student-facing UI.
9. **Assumed default (dismissed, veto if wrong):** if a new screening for the same Student is created/activated while a request is still `PENDING` (e.g. a renewal after `VERIFICATION_EXPIRED`), auto-reject the pending request with `decision_reason = "SUPERSEDED_BY_NEW_COR"` (reviewer = NULL, system). Prevents stale approvals against outdated data. Applied in the register/resubmit/renewal paths.
10. **Assumed default (veto if wrong):** reject requires a `reason` (max 500), matching ADR-024's "rejection requires the reviewer's comment". Approve takes no body.

## Out of scope (explicit)

- Post-activation self-service editing. Eligibility is only `account_status = PENDING_VERIFICATION` with the latest screening `AWAITING_CONFIRMATION`; after activation the screening is `PASSED`, so no further Student requests. Counselor academic corrections remain as-is.
- Superadmin editing values before approving (approve-as-submitted or reject only).
- Any Student-facing notification or "my request status" page/endpoint (Superadmin queue + audit only).
- Letting Superadmin approve registration/COR authenticity in general — only this narrow change-request capability is added.
- A TTL/cleanup job for old `PENDING` requests; the queue shows age and they are superseded by a new screening per decision 9.

## Contradiction to resolve (must update contracts)

`docs/USER_ROLES.md:3,17,30` and ADR-003/ADR-030 state Counselor owns academic correction and Superadmin "must not approve a registration / declare a COR authentic / access audit content". This plan keeps the registration boundary (the Student's submission activates; Superadmin only ratifies a correction) but **adds a new Superadmin capability**, so those contracts must be amended (ADR-032 + USER_ROLES).

## Data model

New table `profile_change_requests` (migration `20261002_profile_change_requests`, `down_revision = "20261001_cor_verification_token"`):

| Column | Notes |
|---|---|
| `change_request_id` | PK, BIGINT UNSIGNED autoincrement |
| `student_user_id` | FK `users.user_id`, `ON DELETE CASCADE` |
| `cor_screening_id` | FK `cor_screenings.cor_screening_id`, `ON DELETE CASCADE` (traceability) |
| `status` | `PENDING` \| `APPROVED` \| `REJECTED` (default `PENDING`) |
| `requested_first_name` / `requested_middle_name` / `requested_last_name` | nullable middle |
| `requested_year_level` | int 1–10 |
| `requested_section` | string |
| `reviewed_by_user_id` | FK `users.user_id`, `ON DELETE SET NULL` |
| `reviewed_at` | DATETIME(6) nullable |
| `decision_reason` | String(500) nullable |
| `created_at` | DATETIME(6), `TS_DEFAULT` |

Indexes: `idx_profile_change_requests_status` (`status`), `idx_profile_change_requests_student` (`student_user_id`). Add a `CHECK` for `status` values. Reuse `DATETIME6`/`TS_DEFAULT` from `app/db/mixins.py`.

Register the model in `app/db/base.py` `import_all_models()` and add the migration loader + `.upgrade()` to `backend/app/tests/conftest.py` (new `PROFILE_CHANGE_MIGRATION_FILE` constant + `load_profile_change_migration_module()`).

## Backend

### New module `backend/app/modules/profile_change/`
`models.py`, `repository.py`, `schemas.py`, `service.py`, `router.py` (mirror existing module layout).

- `repository.py`
  - `find_pending_for_student(student_user_id) -> ProfileChangeRequest | None` (non-locking read).
  - `lock_by_id(change_request_id) -> ProfileChangeRequest | None` (`with_for_update`, `populate_existing`).
  - `list(status, page, page_size)` for the queue.
- `schemas.py`
  - `ChangeRequestStatus = Literal["PENDING","APPROVED","REJECTED"]`.
  - `RequestEditRequest` (student): `first_name`, `middle_name?`, `last_name`, `year_level (1–10)`, `section`. **Excludes** `student_number`, `academic_period`, `campus_id`, `program_id` so unknown fields are dropped by Pydantic defaults — plus explicit server-side equality checks against the screening (below).
  - `ProfileChangeRequestResponse` (request fields, status, reviewer, timestamps) + `ChangeRequestStudentSummary`.
  - `ProfileChangeRequestListItem` for the queue: current vs requested values for the diff.
  - `RejectChangeRequestRequest`: `reason: str = Field(min_length=1, max_length=500)` (required).
- `service.py` (Superadmin review)
  - `list_requests(actor, status, page, page_size)` — requires `SUPERADMIN`.
  - `approve(actor, change_request_id)` — lock **student row first, then the request row**; require `status == PENDING` (else `409 CHANGE_REQUEST_NOT_PENDING`); re-validate requested values; apply to `users.first_name/middle_name/last_name` and `student_profiles.year_level/section`; set `APPROVED`/`reviewed_by`/`reviewed_at`; audit `profile_change_approved`; return the updated request. No notification.
  - `reject(actor, change_request_id, reason)` — same locking/status guard; require a non-empty reason; set `REJECTED`/`reason`; audit `profile_change_rejected`. No notification.
  - `supersede_pending(student_user_id, screening_id)` — auto-reject any `PENDING` request with `decision_reason = "SUPERSEDED_BY_NEW_COR"`; called when a new screening is created/activated for the Student (decision 9).
- `router.py` — `/profile-change-requests` (kebab plural):
  - `GET /profile-change-requests` — `SUPERADMIN`; `status` filter (default `PENDING`), pagination.
  - `POST /profile-change-requests/{change_request_id}/approve` — `SUPERADMIN` (no body).
  - `POST /profile-change-requests/{change_request_id}/reject` — `SUPERADMIN`; required `reason`.
  - Register the router in `app/main.py` (or the app router aggregator used today).

### Student action (extend `cor_screening`)
- New endpoint `POST /cor-screenings/request-edit` in `backend/app/modules/cor_screening/router.py`, using the existing `get_screening_actor` dependency (Student session **or** `X-COR-Token`). Body: `RequestEditRequest`.
- New service method `CorScreeningService.request_edit(student, screening, data)` sharing `_confirm_core` preconditions:
  1. Reject if `screening.status != "AWAITING_CONFIRMATION"` (`SCREENING_NOT_CONFIRMABLE`) or evidence expired (`SCREENING_EXPIRED`, existing logic).
  2. Validate `student_number` (uppercased, `STUDENT_NO_RE`, must equal `extracted_student_number` → `STUDENT_NUMBER_MISMATCH`) and `academic_period` (must equal `extracted_academic_period` when present → new `FIELD_NOT_EDITABLE`).
  3. Validate `campus_id`/`program_id`: must equal the COR-mapped ids when mapped; otherwise must be an active reference row (existing `_assert` behavior). A differing mapped campus/program → `FIELD_NOT_EDITABLE`.
  4. **Do not** run the name/year_level/section mismatch checks of `_assert_fields_match`; instead compute which editable fields differ from the COR-extracted (or, when a field was not extracted, the value the Student supplies).
  5. **Activate with the COR-verified values** (extracted value when present, else the supplied value) using the same activation block as `_confirm_core` (profile upsert, `ACTIVE`, `valid_until`, `PASSED`, `confirmed_at`, `_clear_verification_token`, commit, `_purge_cor_files`, `account_activated` audit).
  6. If no editable field actually differs → behave exactly like confirm (no request row). Otherwise: lock the Student row (already locked), assert no existing `PENDING` request for the Student (else `409 CHANGE_REQUEST_PENDING`), insert the `PENDING` request, audit `profile_change_requested`, and include it in the response.
- Refactor so the activation block is shared (`_activate(student, screening, values)`) and `_confirm_core` delegates to it, to avoid duplicating the activation logic.
- Supersession (decision 9): when `register_with_cor` / `resubmit` creates or re-activates a screening for a Student who has a `PENDING` request, call `ProfileChangeService.supersede_pending(...)` in the same transaction.
- Response: `RequestEditResponse { screening, user, profile, change_request }`.
- Keep `confirm`/`reject`/`resubmit` behavior unchanged (except the supersession call).

### Error codes (stable)
- `FIELD_NOT_EDITABLE` (422) — attempt to change an excluded field.
- `CHANGE_REQUEST_PENDING` (409) — a pending request already exists.
- `CHANGE_REQUEST_NOT_PENDING` (409) — approving/rejecting a non-pending request.
- `CHANGE_REQUEST_NOT_FOUND` (404).
- Reuse `FORBIDDEN_ROLE` (403), `SCREENING_NOT_CONFIRMABLE`, `SCREENING_EXPIRED`, `STUDENT_NUMBER_MISMATCH`.

### Audit
- Audit event types: `profile_change_requested`, `profile_change_approved`, `profile_change_rejected` on `target_type = profile_change_request`.
- No student notification in v1 (user decision): decisions are persisted + audited only.

## Frontend

- `services/apiClient.js` — no change (custom headers already supported; token path already bypasses CSRF).
- `features/accounts/useRegistration.js` — add `requestEdit(fields)` returning `{ success, changeRequest, message }`; keep `confirm`.
- `features/accounts/useCorScreening.js` — add `requestEdit(fields)` calling `POST /cor-screenings/request-edit`; extend error messages with the new codes.
- `pages/RegisterPage.jsx` (modal confirm phase)
  - Keep `student_number` and `academic_period` read-only; keep matched `campus`/`program` read-only.
  - Make `first_name`/`middle_name`/`last_name`/`year_level`/`section` editable, with an "Edit information" affordance.
  - When any editable value differs from the extracted value, show **"Submit edit request"** (posts with `X-COR-Token`, using `tokenHeaders`) instead of/in addition to Confirm; on success go to the `done` phase with copy that states the account is active **and** the change is pending Superadmin approval.
  - Unchanged values still use the normal Confirm.
- `pages/student/RegistrationStatusPage.jsx` — same edit affordance using the session-authorized `useCorScreening.requestEdit`.
- `pages/counselor/CounselorUsersPage.jsx` — add a Superadmin-only "Pending edit requests" section (visible when `canRecover` / role is `SUPERADMIN`): fetch `GET /profile-change-requests?status=PENDING`, render each Student with current→requested diff and age, Approve, and Reject (required reason); toast + refresh on success.
- `features/accounts/useUserDirectory.js` (or a small `useProfileChangeRequests.js`) — data hook for the queue.
- Add a small Superadmin endpoint dependency to the components; no nav change needed (queue lives on `#users`).

## Documentation

- `.ai/DECISIONS.md` — add **ADR-032**: Superadmin ratifies Student-initiated profile edits during verification; explicitly carve it out of ADR-030's "no registration/COR approval" prohibition; restate that Superadmin still does not declare a COR authentic.
- `docs/USER_ROLES.md` — add the capability to Superadmin and reconcile lines 3/17/30.
- `docs/REGISTRATION_VERIFICATION.md` — editable/excluded fields, activation-with-edit semantics, pending request, one-at-a-time, re-request after reject.
- `docs/API_CONTRACT.md` — registration/COR table rows for `POST /cor-screenings/request-edit` and the `/profile-change-requests` set; error codes.
- `docs/SECURITY.md` — new authorization boundary (Superadmin-only queue; excluded fields cannot be changed; audit only, no notification).
- `docs/DATABASE.md` — new table note.
- `.ai/NAMING_CONVENTIONS.md` — `profile_change_requests` table + `change_request_id`; `PENDING`/`APPROVED`/`REJECTED` status values; new endpoint resource.
- `docs/WORKFLOWS.md` — account-lifecycle branch for edit request → Superadmin decision.
- `.ai/CURRENT_TASK.md` — new task entry.

## Tests

Backend (unit + MySQL-gated integration, mirroring existing patterns):
- request-edit activates with COR values and creates a `PENDING` request when an editable field differs;
- no-difference request behaves like confirm (no request row);
- changing `student_number`/`academic_period`/mapped `campus_id`/`program_id` → `422 FIELD_NOT_EDITABLE`;
- second submission while pending → `409 CHANGE_REQUEST_PENDING`;
- token-authorized request-edit works with no cookie; invalid/empty token still fails closed;
- Superadmin approve applies names + year_level + section; reject (required reason) keeps originals; non-Superadmin → `403`; deciding a non-pending request → `409`;
- a new screening created while a request is `PENDING` auto-rejects it with `SUPERSEDED_BY_NEW_COR`;
- audit events recorded; no notification side effects.
- Register the new migration in conftest so MySQL runs execute.

Frontend (`node --test` CJS with `react-test-renderer`):
- modal: editing an allowed field exposes "Submit edit request", posts with `X-COR-Token`, shows the pending-approval done state; student_number/academic_period remain read-only;
- `#registration`: same via session;
- Superadmin queue: renders diff, Approve/Reject call the right endpoints and refresh; visible only to Superadmin.

OpenAPI: regenerate `contracts/openapi.json` and pass `python scripts/export_openapi.py --check`.

## Validation commands

- `backend/`: `COUNSELCONNECT_TEST_DATABASE_URL=... pytest app/tests -q` (expect the new MySQL tests to run, not skip).
- `backend/`: `python scripts/export_openapi.py` then `--check`.
- Manual smoke: register → edit a name → submit → account ACTIVE, request `PENDING`; Superadmin `#users` queues it → approve → names/year_level/section updated; reject path unchanged values.
- `frontend/`: `npm test` (pre-existing 3 calendar failures remain) and `npm run build`.

## Risks / notes

- **Governance:** this weakens ADR-030's boundary; ADR-032 must be explicit so the carve-out is intentional, not an accident.
- **UX:** between activation and approval the Student sees the COR values, not their requested values; there is no Student-facing outcome in v1 (Superadmin queue + audit only). Flag if a status banner is wanted later.
- **Trust:** approved names/section are not COR-verified; Superadmin is the only control. Names are personal data — keep audit minimal and never log full old/new values.
- **Concurrency:** rely on the Student row lock (acquired in `get_screening_actor`/`_lock_student`) to serialize request creation; approve/reject lock Student then request row.
- Existing pre-existing frontend calendar test failures are unrelated and stay red unless separately fixed.

## Ordered tasks

1. Migration `20261002_profile_change_requests` + SQLAlchemy model + `import_all_models` + conftest loader/upgrade.
2. `profile_change` module: repository, schemas, service (list/approve/reject/supersede + audit), router; register router.
3. `cor_screening`: extract shared activation helper; add `request_edit` service + `POST /cor-screenings/request-edit` (token-or-session) + `RequestEditResponse`; add error codes; wire supersession into register/resubmit.
4. Backend tests (unit + integration) incl. token, role, and supersede cases; run MySQL suite + OpenAPI check.
5. Frontend: `useRegistration.requestEdit`, `useCorScreening.requestEdit`, RegisterPage and RegistrationStatusPage edit affordances + done copy.
6. Frontend: Superadmin pending-edit queue on `CounselorUsersPage` + data hook + tests.
7. Docs: ADR-032, USER_ROLES, REGISTRATION_VERIFICATION, API_CONTRACT, SECURITY, DATABASE, NAMING_CONVENTIONS, WORKFLOWS, CURRENT_TASK.
8. Final review focused on authorization (Superadmin-only review, excluded-field enforcement), concurrency, audit, supersession, and the ADR-030 carve-out.
