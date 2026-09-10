# CounselConnect — System Overview

CounselConnect centralizes University of Caloocan City guidance workflows for Students, limited Guidance Staff, and Guidance Counselors.

| Area | Core contract |
|---|---|
| Registration | Current COR → Staff/Counselor review → time-bounded active account |
| Appointments | Counselor slots → Student request → Counselor decision/outcome |
| Messaging | One Student ↔ one Counselor; 30-day post-closure body retention |
| SOS | Five-question rule flow, Counselor alert, approved contact fallback |
| Expression cue | Optional ~3-second local scan; session-only context, never SOS input |
| Wellness resources | Counselor-reviewed internal/external resource cards |
| Assistant | Navigation, approved FAQs, published resources only |
| Operations | Counselor manages CMS, announcements, contacts, accounts/staff, academic corrections, audit views |

Stack: JavaScript (React)/Vite/TailwindCSS, FastAPI, MySQL 8.4 LTS, SQLAlchemy/PyMySQL/Alembic, CapacitorJS, modular monolith.

Global boundaries: backend authorization, data minimization, no diagnosis/medical advice, no raw facial media/biometrics, no durable COR, no unreviewed automated publication, and no mirrored third-party full articles.
