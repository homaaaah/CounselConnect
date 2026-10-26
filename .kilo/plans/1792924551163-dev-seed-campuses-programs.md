# Plan: Gate Student access to the session record

**Risk:** HIGH (authorization change; small surface)
**Current behavior:** a Student can read a FINAL assessment while the appointment is still `CONFIRMED`; drafts already return 404.
**Target:** the Student can read the assessment only when the record is `FINAL` **and** the appointment is `COMPLETED`. Files remain available.

## Decisions

- "Finished" means `appointment.status == "COMPLETED"` (Counselor's explicit outcome), not the scheduled end time.
- Only the record/assessment is gated. The Files tab and file endpoints are unchanged so pre-session/in-session uploads keep working.
- Student receives `404 RECORD_NOT_FOUND` (same as drafts) — do not reveal that a record exists.
- No change for the assigned Counselor, Superadmin, or file authorization.

## 1. Backend (the real gate)

`backend/app/modules/appointments/service.py`, `_record_response`:

```python
if not counselor and (
    record is None
    or record.status != "FINAL"
    or appointment.status != "COMPLETED"
):
    raise AppError("RECORD_NOT_FOUND", "No final session record is available.", status_code=404)
```

This covers `GET /appointments/{id}/record` everywhere; no router or schema change. `can_*` flags remain false for Students.

## 2. Frontend (cosmetic consistency)

`frontend/src/components/sessionRecords/SessionRecordWorkspace.jsx`:

```jsx
const tabs = counselor
  ? [["notes", "Notes"], ["record", "Record"], ["files", "Files"]]
  : [
      ...(appointment.status === "COMPLETED" ? [["assessment", "Assessment"]] : []),
      ["files", "Files"],
    ];
const [tab, setTab] = useState(counselor ? "notes" : "files");
```

- Student landing tab becomes Files; the Assessment tab appears only for `COMPLETED`.
- Keep the `#session-record/{id}` link and "Session files" label in `StudentAppointmentsPage.jsx` for `CONFIRMED`/`COMPLETED` (files stay available).
- Do not add a placeholder message that hints at hidden content.

## 3. Tests

`backend/app/tests/integration/test_session_records.py`:
- In `test_draft_is_counselor_only_and_final_assessment_reaches_student`: after finalize on the `CONFIRMED` appointment, assert the Student still gets `RECORD_NOT_FOUND`; then set `appointment.status = "COMPLETED"` (re-fetch + flush, as the reopen test does) and assert 200 with `notepad is None`.
- Add one case: `COMPLETED` + `DRAFT` still returns `RECORD_NOT_FOUND` for the Student.

`frontend/tests/session-records.test.cjs`:
- Change the Student case's `appointment.status` to `"COMPLETED"` and keep asserting the finalized values render.
- Add an assertion with `status: "CONFIRMED"`: no Assessment tab, Files tab present.

## 4. Docs

- `docs/COUNSELING_SESSION_RECORDS.md`: visibility becomes "finalized assessment, only after the appointment is marked `COMPLETED`".
- `docs/API_CONTRACT.md`: `GET /appointments/{id}/record` Student row adds "and the appointment is `COMPLETED`".
- `.ai/DECISIONS.md` ADR-035: add the completion gate.
- `.ai/CURRENT_TASK.md`: ACTIVE → COMPLETED with real results.

## 5. Validation

- `pytest app/tests/integration/test_session_records.py` with `COUNSELCONNECT_TEST_DATABASE_URL` (MySQL 8.4, port 3307).
- `node --test frontend/tests/session-records.test.cjs`; then `npm test` and `npm run build`.
- Manual: Student on a `CONFIRMED` appointment sees Files only; after the Counselor finalizes + marks COMPLETED, reload shows the Assessment.
- HIGH-risk workflow: one independent read-only review of the authorization gate and its tests.

## Out of scope

- Hiding files or the page, time-based access, notifications, changing Counselor drafts, or altering the record data model.
