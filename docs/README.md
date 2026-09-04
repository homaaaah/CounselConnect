# CounselConnect — Documentation Index

Load one owning feature doc plus shared docs only when needed.

| Need | File |
|---|---|
| System map | `SYSTEM_OVERVIEW.md` |
| Roles/permissions | `USER_ROLES.md` |
| Cross-feature sequence | `WORKFLOWS.md` |
| Shared API contract and frontend/backend handoff | `API_CONTRACT.md` |
| Security/privacy | `SECURITY.md` |
| MySQL/ERD boundary | `DATABASE.md` |
| Registration/COR | `REGISTRATION_VERIFICATION.md` |
| Appointments | `APPOINTMENT_SCHEDULING.md` |
| Messaging | `REAL_TIME_MESSAGING.md` |
| SOS | `SOS_TRIAGE.md` |
| Local expression cue | `AI_EMOTIONAL_BASELINE.md` |
| Wellness resources | `WELLNESS_RESOURCE_DISCOVERY.md` |
| Assistant | `VIRTUAL_GUIDANCE_ASSISTANT.md` |
| CMS/announcements | `CONTENT_MANAGEMENT.md` |
| Counselor operations | `COUNSELOR_DASHBOARD.md` |

API/database/source naming lives in `.ai/NAMING_CONVENTIONS.md`. Exact implemented endpoint schemas live in generated `contracts/openapi.json`; do not hand-edit that snapshot. Update one owning contract and only affected cross-references; avoid copying global rules into every feature file.
