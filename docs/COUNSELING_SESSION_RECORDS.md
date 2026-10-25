# CounselConnect — Counseling Session Records

**Status: implemented (v1); corrections and the multi-state lifecycle remain deferred.**

Each appointment has one private counseling-session record, stored in `session_records` (migration `20261025_session_records`).

## Record content

- `notepad`: free-text scratch notes, autosaved while drafting.
- Assessment fields: `presenting_concern`, `session_summary`, `intervention`, `plan`, plus an optional `follow_up_on` date.
- `status`: `DRAFT` or `FINAL`; `finalized_at` is set on finalization.
- Counselors author text only. Records never contain a diagnosis, automated scoring, or medical advice.

## Counselor workflow

1. The assigned Counselor edits the draft during or after the session; changes autosave after a short debounce.
2. On the scheduled session page, the header **Mark as done** (beside **Mark no-show**) saves the current form, requires all four assessment fields, finalizes the record, and completes the appointment in one server transaction. Missing fields return `409 RECORD_INCOMPLETE` with `details.fields`, and neither the record nor the appointment changes.
3. On the standalone session record page (including after a History completion), **Finalize record** requires all four fields and finalizes only; it does not change the appointment status. Finalizing locks the record.
4. A finalized record can be reopened while the appointment is `CONFIRMED` or `COMPLETED`. Once the appointment is `NO_SHOW`, `CANCELLED`, or `REJECTED`, the record is read-only.
5. Records are writable for `CONFIRMED` and `COMPLETED` appointments only.
6. Counselor History **Mark completed** remains independent of record finalization: a Counselor may complete or no-show from History without finalizing. The session-page **Mark as done** is the combined flow.

`DRAFT`/`FINAL` replaces the previously planned five-state lifecycle; scheduled/in-progress/ended remain appointment and slot state.

## Visibility

- The assigned Counselor reads and writes everything, including the notepad.
- The Student reads the **finalized assessment only**, never the notepad, and only after the Counselor has marked the appointment `COMPLETED`. Drafts, `CONFIRMED` sessions (even past their end time), reopened records, and other outcomes return `404 RECORD_NOT_FOUND`.
- Session files follow the same completion rule: the Student can list/upload/download only after the appointment is `COMPLETED`; the Counselor keeps access while `CONFIRMED` or `COMPLETED`. Reopening a finalized record does not re-lock files.
- Superadmin and other roles have no content access.

## Corrections

Still deferred. The approved intent remains: a Student requests a correction, the assigned Counselor accepts/rejects, and a needed correction is an append-only amendment. Never overwrite or backdate finalized content.

## Audit, API, retention

- Audit events record ids/actors only: `session_record_finalized`, `session_record_reopened`, `appointment_completed`. Autosaves are not audited, and note/assessment text is never logged or copied into audit rows. Marking an already-finalized session done records only the appointment completion.
- Endpoints: `GET|PUT /appointments/{appointment_id}/record`, `POST /appointments/{appointment_id}/record/finalize`, `POST /appointments/{appointment_id}/record/reopen`, and the session-page header `POST /appointments/{appointment_id}/mark-done`. Responses are `Cache-Control: no-store`.
- Retention is still pending ADR-P12. V1 performs no automatic purge.

Session files are described in `PRIVATE_CLINICAL_DOCUMENTS.md` and stored in `session_documents`.
