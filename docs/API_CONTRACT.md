# CounselConnect — API Contract

## Purpose

This document is the shared integration contract for the React frontend and FastAPI backend. It defines project-wide HTTP rules, the contract handoff process, and how the two developers test independently.

It does not replace an owning feature document or FastAPI's generated OpenAPI schema.

## Sources of truth

Use this order when sources disagree:

1. Approved requirements and durable decisions in `.ai/REQUIREMENTS.md` and `.ai/DECISIONS.md`.
2. The owning feature document in `docs/` for business behavior, permissions, lifecycle, privacy, and pending choices.
3. This file for shared API conventions and frontend/backend coordination.
4. The committed OpenAPI snapshot for the exact implemented paths, parameters, request schemas, response schemas, and status codes.
5. Application code, generated frontend types, mocks, and tests.

Generated OpenAPI describes what the backend currently implements; it does not make behavior correct when it conflicts with an approved requirement or feature contract. Fix the implementation and regenerate the schema.

## Contract status language

- `PLANNED`: discussed but not ready for dependent implementation.
- `AGREED`: frontend and backend may build independently against it.
- `IMPLEMENTED`: present in the generated OpenAPI snapshot and verified by backend contract tests.
- `DEPRECATED`: supported temporarily while consumers migrate.

Do not treat a `PLANNED` route or unresolved project decision as approved behavior.

## HTTP conventions

| Concern | Contract |
|---|---|
| Base path | `/api/v1` |
| Resource paths | Plural `kebab-case`, such as `/appointments` and `/enrollment-verifications` |
| Path variables | Descriptive `snake_case`, such as `{appointment_id}` |
| JSON and query fields | `snake_case`; frontend transport types preserve these names |
| Enums and error codes | `SCREAMING_SNAKE_CASE` |
| Timestamps | ISO 8601 UTC with `Z` |
| Calendar dates | `YYYY-MM-DD` |
| JSON content | UTF-8 `application/json` |
| File upload | `multipart/form-data`; binary content is not embedded in JSON |

Use `GET` to read, `POST` to create or perform an explicit state transition, `PATCH` for allowed partial changes, and `DELETE` only for an approved removal operation. Use action endpoints when a generic update would hide business rules, such as `POST /appointments/{appointment_id}/confirm`.

## Authentication and authorization

- Every non-public operation requires authentication and server-side authorization.
- Authorization must enforce role, ownership, assignment, appointment status/mode/time, and conversation purpose where applicable.
- A hidden or disabled frontend control is not an authorization control.
- Authentication uses revocable opaque sessions stored in MySQL. For the web client, send the random session credential only in a `Secure`, `HttpOnly`, `SameSite=Lax` cookie; store only its cryptographic hash. Do not use JWT refresh tokens or browser `localStorage` for authentication.
- State-changing cookie-authenticated requests require CSRF protection.
- All roles use a one-hour idle timeout and a 12-hour absolute timeout, with a five-minute warning and explicit continuation. Genuine CounselConnect user actions renew idle activity; background polling and WebSocket heartbeats do not. `Remember Me` is excluded from v1.
- Passwords use Argon2id. Password-reset credentials are hashed, single-use, expire after 30 minutes, and successful reset revokes active sessions.
- Exact Capacitor credential transport and production reset-email delivery remain pending under `ADR-P09`.
- Never place credentials, tokens, COR links, message bodies, SOS answers, or other sensitive values in URLs or routine logs.

## Request semantics

- Reject unknown enum values; do not silently map them to a default.
- For `PATCH`, an omitted field means "leave unchanged." An explicit `null` means "clear the field" only when that field is documented as nullable and clearable.
- Validate identifiers, participant scope, state transitions, and cross-field rules on the backend.
- Client-side validation improves usability but does not replace backend validation.
- File type, size, and count limits must come from the owning feature document or an approved decision. COR and internal-resource limits are still pending.

## Success responses

- Return a single resource directly as its response object; do not add a generic `data` wrapper.
- List responses use:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

- A successful resource creation normally returns `201 Created` and the created resource.
- A successful read or state transition normally returns `200 OK` and the current resource representation.
- Use `204 No Content` only when the agreed endpoint intentionally returns no response body.

## Error responses

All handled API errors use this envelope:

```json
{
  "error": {
    "code": "SLOT_UNAVAILABLE",
    "message": "The selected slot is no longer available.",
    "details": {}
  }
}
```

Rules:

- `code` is stable and suitable for frontend branching.
- `message` is safe, human-readable text; it must not contain secrets or internal traces.
- `details` is an object containing safe field-level or conflict context; use `{}` when none is required.
- FastAPI's default validation error must be normalized to this envelope by a shared exception handler.
- `VALIDATION_ERROR` uses `details.fields`, an array of `{ "loc": ["body", "field_name"], "type": "error_type", "message": "Invalid or missing value." }`. Never return submitted `input` values or validator context.
- The frontend must branch on `error.code`, not exact message text.

| Status | Use |
|---|---|
| `400 Bad Request` | Malformed request that is not a schema-validation failure |
| `401 Unauthorized` | Missing, invalid, or expired authentication |
| `403 Forbidden` | Authenticated caller lacks role, ownership, or assignment permission |
| `404 Not Found` | Resource does not exist, or an endpoint deliberately conceals its existence |
| `409 Conflict` | Current state prevents the operation, such as `SLOT_UNAVAILABLE` or an invalid transition |
| `422 Unprocessable Entity` | Field or cross-field validation failed |
| `429 Too Many Requests` | An approved rate limit was exceeded |
| `500 Internal Server Error` | Unexpected failure using a safe generic response |
| `503 Service Unavailable` | Required service is temporarily unavailable |

Exact error codes belong to each agreed endpoint contract and must appear in tests. Do not reuse one generic code for unrelated failures.

## Pagination and filtering

- Paginated routes accept one-based `page` and `page_size` query parameters.
- Default and maximum `page_size` values must be explicit in OpenAPI before the frontend depends on them.
- Filters use canonical `snake_case` field names and uppercase enum values, for example `?status=PENDING`.
- Sort fields and direction must be allowlisted. Do not pass raw database column or SQL fragments from the client.
- Empty results return `200 OK` with an empty `items` array and the pagination metadata, not `404`.

## Concurrency, retry, and duplicate protection

- Appointment booking must reserve the selected slot atomically. A concurrent loser receives `409 Conflict` with a stable code such as `SLOT_UNAVAILABLE`.
- State-transition endpoints revalidate the current resource state inside the transaction.
- Message sends should accept the agreed client message identifier so a safe retry does not create a duplicate message.
- Do not automatically retry non-idempotent requests unless the endpoint explicitly defines duplicate protection.
- A generic `Idempotency-Key` policy is not approved; add one only through a documented contract change.

## Feature-specific boundaries

### Registration and COR

- COR uploads use `multipart/form-data` and private temporary storage outside MySQL.
- API responses must not expose public or durable COR URLs.
- Assigned Guidance Staff may access only their assigned verification cases; Counselor retains the approved broader authority.

### Appointments

- Slot `delivery_mode` is `ONLINE`, `FACE_TO_FACE`, or `BOTH`.
- Student-selected `appointment_mode` is `ONLINE` or `FACE_TO_FACE` and must be compatible with the slot.
- A face-to-face booking returns the appointment's `meeting_location` snapshot. It does not depend on later campus-location edits.
- Only Counselor may mutate `guidance_office_location`.
- A confirmed online appointment may obtain exactly one `APPOINTMENT` conversation when the approved start-time rule allows it.

### Messaging

- `conversation_type` is `GENERAL`, `APPOINTMENT`, or `SOS`.
- Every operation revalidates the authorized Student, Counselor, purpose, and source linkage.
- Raw camera media and embeddings never enter message or API payloads.
- Real-time transport, delivery/read semantics, attachment support, message-size limits, and any pre-start appointment window remain pending.

### SOS and assistant

- SOS responses and rules remain non-diagnostic and use only approved questions and thresholds.
- Assistant responses are bounded to approved navigation, FAQ, and published resources.
- Do not disclose confidential Student data to external services.

## OpenAPI handoff

FastAPI exposes the live generated schema at `/openapi.json` and interactive documentation at `/docs` while the backend is running. The team must also commit a generated snapshot at `contracts/openapi.json` whenever an `AGREED` endpoint is implemented or changed.

Do not hand-edit the generated snapshot. Change the FastAPI route, Pydantic schema, response declaration, or shared error handler, then regenerate it.

From `backend/`, run `python scripts/export_openapi.py` to regenerate, or add `--check` to verify the snapshot without changing it. Neither command starts the cleanup worker or connects to MySQL.

The snapshot is ready for frontend use only when:

- the endpoint's method, path, auth requirement, request body, success response, error responses, and status codes are declared;
- required/optional/nullable fields are distinguishable;
- examples contain synthetic data only;
- backend contract tests pass; and
- the snapshot diff is included in review.

## Independent developer workflow

### Before parallel implementation

For every new or changed endpoint, frontend and backend agree on this record in the task or pull request:

```text
Contract status: AGREED
Feature requirement ID:
Method and path:
Authentication/allowed roles:
Path and query parameters:
Request schema and example:
Success status/schema and example:
Error statuses/codes:
Important business rules:
Open questions: none
```

If `Open questions` is not `none`, keep the contract `PLANNED` and resolve the governing decision before both sides implement it.

### Backend developer

1. Implement the route and Pydantic schemas from the agreed record and owning feature document.
2. Add authorization, state, concurrency, privacy, and error-envelope tests.
3. Test with FastAPI's test client against an isolated test database/storage substitute.
4. Generate and commit `contracts/openapi.json`.
5. Confirm the OpenAPI diff matches the agreed record; do not silently change the contract.

### Frontend developer

1. Use `contracts/openapi.json` to generate or validate API transport types.
2. Build an MSW mock for the agreed success and error examples.
3. Test loading, empty, success, validation, forbidden, conflict, and server-failure states as applicable.
4. Keep DTO fields `snake_case` at the API boundary; map explicitly to UI models only when useful.
5. Replace the mock base URL with the real development API without changing component behavior.

### Integration check

Run the same agreed request/response examples against the real backend. Integration is complete only when the frontend tests, backend tests, OpenAPI snapshot check, and at least one real frontend-to-backend flow pass.

## Contract-change process

1. Identify the owning requirement and feature document.
2. Resolve any new business or privacy decision before editing schemas.
3. Mark the endpoint change `AGREED` and review its compatibility impact.
4. Update backend schemas/tests and regenerate OpenAPI.
5. Update frontend types/mocks/tests in the same change set or coordinated dependent change.
6. For a breaking public contract, prefer a migration period; introduce a new API version only for a deliberate incompatible boundary, not every field addition.

Never make an undocumented response-field or enum change solely to satisfy one side's implementation.

## Review checklist

- [ ] Requirement ID and owning feature document are identified.
- [ ] No pending decision was guessed.
- [ ] Roles, ownership, assignment, and sensitive-data rules are enforced server-side.
- [ ] Request fields, required/optional/null behavior, enums, and examples are explicit.
- [ ] Success and error statuses, codes, and schemas are explicit.
- [ ] OpenAPI, backend tests, frontend types, mocks, and tests agree.
- [ ] Examples and logs contain synthetic, non-sensitive data.
- [ ] Concurrency and retry behavior are tested where applicable.

## Pending project-wide API decisions


- `ADR-P02`: real-time messaging transport and delivery semantics.
- `ADR-P03`: final SOS instrument, thresholds, availability/fallback rule, and retention.
- `ADR-P04`: appointment duration/buffer, cutoffs, reminders, blocked periods, and any join window.
- `ADR-P05`: COR upload limits and exact audit fields.
- `ADR-P07`: internal-resource attachment limits and manual publication rule.
- `ADR-P09`: Capacitor session-credential transport and production password-reset email delivery/fallback.

Until approved, these items must remain absent, optional, or explicitly marked `PLANNED` in endpoint work.
