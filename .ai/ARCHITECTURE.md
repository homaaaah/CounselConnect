# CounselConnect — Architecture

## Shape

```text
JavaScript React/Vite/Tailwind (+ Capacitor)
          │ HTTPS; opaque cookie session
       FastAPI modular monolith
          │ routes → schemas → services → repositories
 SQLAlchemy 2.0 + PyMySQL + Alembic
          │
      MySQL 8.4 LTS
          │ metadata only
 private filesystem/object-storage abstraction
```

REST remains the durable source of truth. Native WebSockets deliver committed chat/session events and planned WebRTC signaling. WebRTC carries live one-to-one audio/video; the application does not record or store media.

## Target modules

`auth`, `accounts`, `enrollment_verification`, `appointments`, `messaging`, `calls`, `counseling_sessions`, `clinical_documents`, `session_observation`, `sos`, `content`, `operations`, and `audit`.

The current `wellness_resources` module is scheduled for removal. Resource-based assistant retrieval is removed; a navigation/FAQ-only assistant remains pending.

Routes own transport, schemas validate contracts, services own authorization/business rules, and repositories own persistence. Cross-module access goes through service contracts. React must not duplicate authoritative business rules.

## Storage boundaries

- MySQL: accounts, academic profiles, COR/OCR/barcode screening metadata, appointments, messages, session records, amendments, document metadata, and audit metadata.
- Temporary private COR store: delete after processing/replacement/expiry.
- Durable private clinical-document store: development filesystem root configured outside public paths; production provider pending.
- Browser/device memory: optional AI observation and WebRTC media; never durable.
- No public/static directory serves private files.

## Critical flows

- Registration: email/password + COR → file validation → format classification → OCR/extraction → embedded-barcode decode/consistency checks → reference/academic-period checks → Student confirmation → activate or resubmit → delete temporary COR.
- Authentication: Student Number or email + password → opaque session → role/ownership authorization.
- Appointment: recurring schedule/blocks → Student selects slot/mode and states concern → atomic `PENDING` request → Counselor decision/outcome.
- Online session: lobby → explicit join → durable text conversation + optional WebRTC call → Counselor ends session → documentation/final outcome.
- Counseling record: editable Counselor draft → finalized immutable assessment → Student read-only access → correction request → Counselor-authored append-only amendment.
- History: assigned Counselor opens current session → purpose-bound read of relevant finalized prior-session data → audited access.
- Clinical document: authorized upload → validation/private storage → metadata in MySQL → authorized backend-streamed retrieval.
- AI observation: explicit consent → Counselor-triggered local observation + optional Student self-report → session-only non-diagnostic summary → discard; Counselor independently authors assessment.
- SOS: approved questions/rules → case/alert/fallback; AI observation remains independent.
- Superadmin: administrative oversight only; counseling-content access is denied unless a separately approved exceptional policy exists.

## Migration boundary

The target architecture is not yet fully implemented. Existing Guidance Staff/manual COR review, text-only session limits, missing counseling-record tables, and Wellness Resource code must be changed through reviewed Alembic and application migrations. Preserve the v4.1 baseline as historical; do not rewrite deployed databases manually.

## Non-goals

No microservices, distributed event bus, autonomous diagnosis, medication advice, biometric identity recognition, cloud facial analysis, call recording, automatic transcript/summary, persistent AI observation history, or unapproved Superadmin access to counseling content.
