# CounselConnect — Current Task

**Status:** PLANNING / NOT YET IMPLEMENTED  
**Program:** Advisor-directed system revision

## Objective

Migrate the working CounselConnect prototype to the approved target design without breaking authentication, recurring appointment scheduling, scheduled text chat, or existing data.

## Approved target changes

1. Replace manual Guidance Staff COR review with automated COR format matching, OCR/data extraction, embedded-barcode screening, reference-data checks, and Student confirmation.
2. Permit Student login by Student Number or registered email.
3. Replace the target role set with `STUDENT`, `COUNSELOR`, and `SUPERADMIN`.
4. Preserve support for multiple Counselor accounts and assignment-scoped data.
5. Add concern category/details to appointment requests.
6. Add planned one-to-one WebRTC audio/video to confirmed online sessions without recording.
7. Add Counselor draft notes, finalized assessments, session tracking, prior-session history, Student read-only assessment access, and append-only amendments.
8. Add private external diagnosis/prescription/referral document uploads.
9. Expand the optional emotional feature into an AI-assisted multimodal observation panel using observable cues, Student self-report, and session trends; no diagnosis or persistence.
10. Remove the Wellness Resource Library and automated resource discovery.

## Important limitations

- COR format matching, OCR, and barcode screening check structure and internal consistency; they do not prove UCC issued the file.
- Authoritative verification of decoded barcode data against a University-controlled source remains pending.
- Superadmin has no default access to counseling content.
- The Counselor, not AI, authors every durable assessment.
- Raw call media, recordings, transcripts, automatic summaries, facial media, embeddings, and AI observation history remain forbidden.
- The production private-storage provider and final clinical-record retention periods remain pending.
- The future of a navigation/FAQ-only assistant remains pending.

## Migration sequence

1. Update ADRs/contracts and freeze the current implementation checkpoint.
2. Add `SUPERADMIN` while temporarily preserving current roles.
3. Build automatic COR format/OCR/barcode screening alongside the manual path and validate it with unseen sanitized samples, including missing, unreadable, invalid, and mismatched barcodes.
4. Switch registration to automated screening, migrate/deactivate Guidance Staff, then remove Guidance Staff authorization/routes/UI.
5. Add appointment concern.
6. Add counseling-session records, finalized assessment access, and amendment workflow.
7. Add private clinical-document storage abstraction and uploads.
8. Add WebRTC calling and authenticated signaling.
9. Add optional AI-assisted session observation.
10. Disable/remove Wellness Resource routes/UI/code, migrate or delete development data, and drop resource tables.
11. Regenerate OpenAPI, run MySQL migrations/tests, update diagrams, and verify full flows.

## Contracts to preserve

- Opaque cookie sessions, CSRF, one-hour idle, 12-hour absolute expiry, and no Remember Me.
- Weekly schedules, temporary blocks, slot materialization, booking locks, appointment ownership, mode/location rules, and scheduled text-chat behavior.
- Message-body retention remains separate from durable assessments.
- SOS remains rule-based and independent from AI observation.
- UTC persistence and Asia/Manila display.
- v4.1 remains the historical baseline; new schema changes use Alembic.

## Next action

Before source-code changes, agree on the exact database/API design for role migration and automated COR screening, including template-specific barcode rules and safe metadata. Do not remove Guidance Staff until the replacement registration path is implemented and tested.