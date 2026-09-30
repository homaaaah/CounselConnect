# CounselConnect — Requirements

Use IDs in tasks and tests. These requirements describe the approved target design; implementation status is tracked in `.ai/CURRENT_TASK.md`.

| ID | Requirement |
|---|---|
| FR-REG-01 | Student registers with registered email, password, and current COR. The system validates the file, matches an accepted UCC COR format, performs OCR/data extraction, checks the embedded barcode, and asks the Student to confirm extracted Student Number, name, campus, program, year, section, and academic period. |
| FR-REG-02 | Format matching, OCR confidence, required-field checks, academic-period checks, reference-data consistency, and barcode screening determine automated screening. Barcode screening validates expected presence, readability, configured symbology/payload structure, and consistency with OCR-extracted identifiers when encoded. It must not be described as proof of official issuance without an authoritative University-controlled verification source. |
| FR-REG-03 | A passing confirmed screening activates the account and sets `valid_until`; unreadable, incomplete, unsupported, barcode-missing/unreadable/invalid, or inconsistent submissions require resubmission. Barcode expectations are selected by approved COR template version. Any exceptional override requires a separate approved policy. |
| FR-REG-04 | Temporary COR content is stored privately outside MySQL and deleted after completed processing, replacement, or the approved expiry. |
| FR-AUTH-01 | A Student may sign in using either their unique Student Number or unique registered email and the same password. Counselor and Superadmin accounts sign in by email. |
| FR-AUTH-02 | Authentication and backend role/ownership/assignment authorization protect every non-public operation. |
| FR-AUTH-03 | Web authentication uses revocable MySQL-backed opaque sessions in secure HttpOnly cookies with CSRF protection; passwords use Argon2id and raw credentials are never persisted or logged. |
| FR-AUTH-04 | Every role uses a one-hour idle and 12-hour absolute session limit with a five-minute warning; genuine activity may renew idle time, heartbeats may not, and v1 has no Remember Me. |
| FR-ROLE-01 | Target roles are `STUDENT`, `COUNSELOR`, and `SUPERADMIN`. Guidance Staff is removed after automatic COR screening replaces the manual workflow. |
| FR-ROLE-02 | The system supports multiple Counselors. Counselor-owned schedules, appointments, conversations, assessments, and documents remain scoped by assignment and purpose. |
| FR-ROLE-03 | Superadmin manages accounts, Counselor provisioning, reference data, system configuration, correction requests, and operational audit, without default access to counseling content. |
| FR-APPT-01 | Counselors create recurring weekly schedules or concrete availability; Students request slots; assigned Counselors confirm/reject and record outcomes; temporary blocks represent unavailable time. |
| FR-APPT-02 | Each Student appointment request includes a required concern category and an optional length-limited concern description visible only to the Student and assigned Counselor. |
| FR-APPT-03 | Slots support `ONLINE`, `FACE_TO_FACE`, or `BOTH`; a face-to-face booking stores the configured campus Guidance Office location as a snapshot. |
| FR-MSG-01 | An authorized Student and assigned Counselor exchange secure durable text messages in an appointment-linked conversation. |
| FR-CALL-01 | A confirmed online appointment may provide an authorized one-to-one WebRTC audio/video call during its approved session window. Signaling is authenticated; media is not recorded or stored. |
| FR-SESSION-01 | Each counseling appointment may own one counseling-session record with lifecycle states separate from appointment status. |
| FR-SESSION-02 | Counselor notes are editable drafts until finalized. A finalized assessment is immutable; corrections use append-only Counselor-authored amendments through an audited request workflow. |
| FR-SESSION-03 | During an authorized session, the assigned Counselor may view the Student's relevant finalized prior-session history, recommendations, referrals, follow-ups, amendments, and approved document metadata. |
| FR-SESSION-04 | Students may read their own finalized assessments and amendments but cannot read Counselor draft notes or internal administrative comments. |
| FR-DOC-01 | Students and authorized Counselors may upload private external diagnosis, prescription, referral, and approved clinical documents as PDF/JPEG/PNG subject to validation and policy limits. |
| FR-DOC-02 | Clinical file content stays outside MySQL and public/static paths. MySQL stores metadata, ownership, linkage, checksum, retention, and audit references only. |
| FR-AI-01 | An optional Counselor-triggered AI-assisted multimodal session observation may combine local facial-expression cues, Student self-report, appointment concern, and observation trends. |
| FR-AI-02 | AI output uses observable labels and model confidence, remains session-only, and never claims depression, anxiety, another diagnosis, clinical certainty, suicide risk, or treatment advice. |
| FR-AI-03 | AI observations never automatically change SOS results, appointment/session status, assessment content, or access. Only the Counselor authors the durable assessment. |
| FR-SOS-01 | SOS validates the approved questions, applies approved rules, creates/alerts cases when required, and shows approved fallback contacts. AI observations never affect SOS logic. |
| FR-OPS-01 | Superadmin manages authorized accounts, Counselors, reference data, configuration, correction requests, and operational audit. Counselor manages their own schedules, assigned sessions, assessments, and authorized clinical documents. |
| FR-CONTENT-01 | Approved structured Guidance Office content, FAQs, announcements, and emergency contacts remain supported. |
| FR-RES-01 | The Wellness Resource Library, manual resource publication, and automated resource discovery are removed from target scope. |
| FR-AST-01 | Resource-based assistant retrieval is removed. Whether a navigation/FAQ-only assistant remains is pending ADR-P13. |
| FR-MOB-01 | Core workflows support desktop and Capacitor-oriented mobile use. |
| PR-COR-01 | COR files are temporary private artifacts, never MySQL blobs, public URLs, or long-lived backups; cleanup failures remain detectable and retryable. |
| PR-COR-02 | Raw decoded barcode payloads are not persisted or logged. MySQL may retain the screening status, symbology, confidence, SHA-256 payload digest, and derived comparison results needed for audit-safe troubleshooting. |
| PR-CLIN-01 | Assessments, counseling history, and clinical documents are sensitive purpose-bound records with least-privilege access and minimal audit metadata. |
| PR-MEDIA-01 | Do not store raw call media, facial images/frames, embeddings, call recordings, generated transcripts, automatic summaries, or AI observation history. |
| PR-MSG-01 | Message bodies retain the approved 30-day post-closure policy unless a later retention decision supersedes it. Durable assessments are separate from chat messages. |
| SAFE-01 | The system does not diagnose, prescribe, recommend medication, or replace a qualified Counselor or external clinician. |
| NFR-01 | Maintain a testable modular monolith appropriate for a small university team. |
| NFR-02 | Store and transmit only necessary data; use UTC, explicit failure states, and safe migrations. |

Missing behavior is an open requirement, not permission to invent it.
