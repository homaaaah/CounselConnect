# CounselConnect — AI Development Rules

## Authority

Conflict order: current human/adviser instruction → latest approved decision → owning feature doc → requirements → architecture → implementation/tests. Report unresolved material conflicts; do not invent policy.

## Work discipline

- Load only the context route needed for the task.
- Inspect affected code/tests first; make the smallest coherent change.
- For data-driven UI redesigns or refactors, follow [UI_CHANGE_SAFETY.md](UI_CHANGE_SAFETY.md): declare preserved contracts, verify list completeness and record identity, and test behavior through the API boundary.
- Reuse existing modules; do not silently replace stack, auth, persistence, transport, or business rules.
- Follow `.ai/NAMING_CONVENTIONS.md` for APIs, models, database objects, events, and files.
- Backend authorization is authoritative; hidden UI is not access control.
- Validate all inputs, uploads, CMS data, and external metadata. Externalize secrets and use safe database access.
- Keep confidential data out of logs, errors, URLs, analytics, and unapproved external services.

## Privacy/safety invariants

- COR screening: private temporary storage, OCR/format checks only, Student confirmation, and cleanup logging without file content. Do not claim University authenticity; QR/registrar verification is pending.
- Counseling access: support multiple Counselors and enforce assignment. Superadmin has no default access to chats, drafts, assessments, clinical files, SOS answers, or call media.
- Assessments: Counselor drafts are private; finalized assessments are immutable; corrections use append-only Counselor-authored amendments; Students receive read-only final access.
- Clinical files: store bytes through private storage, metadata/opaque keys in MySQL, and serve only through authorization-checked no-store responses.
- Calls/AI: no recordings, generated transcripts, summaries, raw media, facial embeddings, or persisted AI observation history. AI remains optional, consented, non-diagnostic, and outside SOS.
- Messaging: purge message bodies 30 days after conversation closure under the existing rule.
- Wellness Resource discovery/library is removed; do not create new dependencies on legacy resource code.
- No automated psychological diagnosis, medication recommendation, or replacement of Counselor judgment.

## Data and tests

- MySQL 8.4 LTS; SQLAlchemy 2.0 + PyMySQL; Alembic. No PostgreSQL-specific assumptions or manual deployed-schema patching.
- Use UTC in storage/API; display `Asia/Manila`.
- Behavior/API/data/security changes require focused automated tests where practical. Always test touched authorization/privacy boundaries.
- Never claim checks passed unless run.

## Documentation

Update only the owning contract plus affected requirement/decision/routing references. Routine progress belongs in `CURRENT_TASK.md` or version-control history, not stable docs.

Completion report: outcome, files changed, checks run, unresolved limitations/decisions.
