# CounselConnect — Private Clinical Documents

**Status: approved target; planned implementation.**

Students and assigned Counselors may upload authorized external referral, diagnosis, prescription, or other approved clinical documents as PDF, JPEG, or PNG.

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
