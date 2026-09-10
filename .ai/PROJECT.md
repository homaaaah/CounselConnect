# CounselConnect — Project Context

CounselConnect is a University of Caloocan City guidance platform for Students, Guidance Staff, and Counselors.

## Product areas

- Registration and temporary COR verification
- Counselor-managed appointment availability and Student booking
- Student–Counselor messaging and appointment-linked chat
- SOS case handling and Counselor presence
- Counselor-reviewed wellness resources and announcements
- Assistant navigation and approved FAQ/resource responses
- Counselor operations, account management, and audit views

## Technology

The system is a modular monolith:

- Frontend: JavaScript, React, Vite, TailwindCSS, and CapacitorJS
- Backend: FastAPI with SQLAlchemy 2.0 and PyMySQL
- Database: MySQL 8.4 LTS, managed with Alembic

Backend routes handle transport, schemas validate contracts, services enforce authorization and business rules, and repositories handle persistence. Web authentication uses secure HttpOnly opaque sessions with CSRF protection.

## Project boundaries

- Backend authorization is authoritative.
- Store timestamps in UTC and display them in Asia/Manila.
- COR files are private and temporary; delete them after a decision or seven-day expiry.
- Facial-expression processing is optional, local-device only, session-only, and non-diagnostic.
- Do not store biometrics, raw facial media, durable assistant history, or mirrored third-party articles.
- Wellness content requires Counselor review before publication.
- The system does not diagnose or provide medical recommendations.

## Related authorities

- [Architecture](ARCHITECTURE.md) — module boundaries and critical flows
- [Requirements](REQUIREMENTS.md) — approved product behavior
- [Naming conventions](NAMING_CONVENTIONS.md) — canonical names and values
- [Decisions](DECISIONS.md) — approved architectural decisions
