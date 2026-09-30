# CounselConnect — Project Context

CounselConnect is a University of Caloocan City guidance and counseling platform for Students, Guidance Counselors, and Superadmins. The target design supports multiple Counselor accounts; no singleton Counselor assumption is allowed.

## Product areas

- Student registration through COR format validation, OCR/data extraction, embedded-barcode screening, and Student confirmation
- Student login by Student Number or registered email
- Counselor-managed recurring availability, temporary blocks, and Student appointment booking
- Appointment concerns, scheduled text chat, and planned one-to-one audio/video counseling
- Counselor-authored session notes, finalized assessments, follow-up plans, and Student session history
- Private Student/Counselor uploads of external diagnosis, referral, and prescription documents
- Optional AI-assisted multimodal session observation for Counselor context
- SOS case handling and Counselor presence
- Superadmin account, reference-data, configuration, correction-request, and operational oversight
- Structured Guidance Office content, FAQs, announcements, and emergency contacts

The Wellness Resource Library and automated resource-discovery feature are removed from the target scope.

## Technology

The system remains a modular monolith:

- Frontend: JavaScript, React, Vite, TailwindCSS, and CapacitorJS
- Backend: FastAPI with SQLAlchemy 2.0 and PyMySQL
- Database: MySQL 8.4 LTS, managed with Alembic
- Real-time transport: REST for durable state, native WebSockets for committed events/signaling, and planned WebRTC for one-to-one audio/video
- Development private storage: configurable filesystem root outside public/static paths

Routes handle transport, schemas validate contracts, services enforce authorization and business rules, and repositories handle persistence. Web authentication uses secure HttpOnly opaque sessions with CSRF protection.

## Project boundaries

- Backend authorization is authoritative.
- Store timestamps in UTC and display them in Asia/Manila.
- COR format matching, OCR, and embedded-barcode screening check structure and data consistency. Barcode decoding alone does not prove that UCC issued the document; authoritative University verification remains pending.
- Do not persist or log raw decoded barcode payloads; keep only approved screening metadata and derived match results.
- COR files are private and temporary; delete them after processing or the approved expiry.
- Clinical documents are private durable files outside MySQL; MySQL stores metadata only.
- Superadmin performs administrative oversight and has no default access to counseling content.
- Finalized assessments are immutable; corrections use append-only Counselor-authored amendments.
- Students may read their own finalized assessments but not Counselor draft notes.
- AI may describe optional observable/self-reported indicators and confidence, but never diagnose, prescribe, or replace the Counselor.
- Do not persist raw audio/video, facial images, embeddings, AI observation history, call recordings, generated transcripts, or automatic summaries.
- The system does not issue medical diagnoses or recommendations.

## Implementation status

The current code still contains Guidance Staff/manual COR review and Wellness Resource modules. The approved target above requires staged migrations and must not be treated as already implemented. See `.ai/CURRENT_TASK.md`.

## Related authorities

- [Architecture](ARCHITECTURE.md)
- [Requirements](REQUIREMENTS.md)
- [Naming conventions](NAMING_CONVENTIONS.md)
- [Decisions](DECISIONS.md)
