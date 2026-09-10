# CounselConnect — Project Context

- **Client:** University of Caloocan City Guidance and Counseling Office
- **Goal:** centralized student guidance workflows plus Counselor-reviewed wellness resource discovery
- **Team:** four-person capstone team
- **Users:** Student, Guidance Staff, Guidance Counselor
- **Architecture:** modular monolith
- **Stack:** React + Vite + TailwindCSS; FastAPI; MySQL 8.4 LTS; SQLAlchemy 2.0 + PyMySQL; Alembic; CapacitorJS

## Feature ownership

| Area | Contract |
|---|---|
| Accounts/enrollment verification | `docs/REGISTRATION_VERIFICATION.md` |
| Appointments | `docs/APPOINTMENT_SCHEDULING.md` |
| Messaging | `docs/REAL_TIME_MESSAGING.md` |
| SOS | `docs/SOS_TRIAGE.md` |
| Optional local expression cue | `docs/AI_EMOTIONAL_BASELINE.md` |
| Wellness resources | `docs/WELLNESS_RESOURCE_DISCOVERY.md` |
| Virtual assistant | `docs/VIRTUAL_GUIDANCE_ASSISTANT.md` |
| CMS/announcements | `docs/CONTENT_MANAGEMENT.md` |
| Counselor operations | `docs/COUNSELOR_DASHBOARD.md` |
| Roles/security/data | `docs/USER_ROLES.md`, `docs/SECURITY.md`, `docs/DATABASE.md` |

## Stable scope

- Student accounts activate only after current-COR approval and remain usable through `valid_until`.
- Guidance Staff performs assigned COR verification only. Counselor is the highest-authority role and owns counseling plus operational/admin functions.
- Appointments use concrete availability slots and Counselor approval.
- Messaging is one Student ↔ one Counselor; bodies are deleted 30 days after closure.
- SOS is an approved rule-based flow; optional expression output is context only.
- Automated resources remain `PENDING` until Counselor review; published cards redirect to canonical sources.
- Assistant answers navigation, approved FAQs, and published resources only; it keeps no persistent chat history.

Open choices are only in `.ai/DECISIONS.md`.
