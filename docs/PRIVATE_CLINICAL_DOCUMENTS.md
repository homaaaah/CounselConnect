# CounselConnect — Private Clinical Documents

**Status: approved target; appointment-scoped session documents implemented (v1).**

Students and assigned Counselors may upload authorized external referral, diagnosis, prescription, or other approved clinical documents as PDF, JPEG, or PNG.

## Implemented v1 subset — session documents

- `session_documents` (migration `20261025_session_records`) attaches files to one appointment, so face-to-face and online sessions use the same flow.
- Allowed types: `.pdf`, `.jpg`/`.jpeg`, `.png`, maximum 10 MB (`COUNSELCONNECT_SESSION_DOCUMENT_MAX_MB`). Validation checks extension, magic bytes (`%PDF-` with `%%EOF`, JPEG/PNG signature), and decodes images with Pillow.
- Storage key is random (`session/<uuid>.<ext>`) under `COUNSELCONNECT_SESSION_DOCUMENT_STORAGE_ROOT` (default `./var/session-documents`, ignored by Git). Path containment is checked on every read/write.
- The assigned Student and Counselor list, upload, and download; only the uploader or the assigned Counselor may delete. Deletion removes the bytes and keeps soft-deleted metadata plus an audit event.
- A Student can access files only after the Counselor marks the appointment `COMPLETED`; before that, every Student file endpoint returns `409 DOCUMENT_ACCESS_CLOSED`. On the scheduled session page, **Mark as done** performs that completion. The Counselor keeps access while the appointment is `CONFIRMED` or `COMPLETED`.
- Reopening a finalized session record does not re-lock session files: file access follows appointment status only, not record status.
- Downloads send `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store`.
- Uploads are allowed only for `CONFIRMED` or `COMPLETED` appointments. Audit events record document ids only (`session_document_uploaded|downloaded|deleted`); filenames and bytes are never logged.
- No automatic purge in v1.

Endpoints: `GET|POST /appointments/{appointment_id}/documents`, `GET /appointments/{appointment_id}/documents/{document_id}/download`, `DELETE /appointments/{appointment_id}/documents/{document_id}`.

## Storage

- MySQL stores metadata, owner/uploader, document type, size, hash, timestamps, authorization link, and opaque storage key.
- File bytes live behind a private storage abstraction, never in a public/static frontend folder or database blob.
- Development uses an environment-configured local path such as storage/private outside public serving.
- Production provider/encryption/backup is pending ADR-P11; final retention is pending ADR-P12.

## Access

- Student: own authorized files.
- Assigned Counselor: files relevant to the active/authorized counseling relationship.
- Superadmin: metadata for operations only; no default content access.
- Retrieval uses authenticated authorization-checked endpoints and Cache-Control: no-store.

Validate extension, MIME/magic bytes, size, image decoding/PDF structure, and safe generated filenames. Quarantine/reject unsafe files; never log file content or expose storage paths.

