# CounselConnect — Minimal Context Map

Always read `.ai/RULES.md` and `.ai/CURRENT_TASK.md`, then only one primary route plus directly affected code/tests.

| Route | Additional files |
|---|---|
| `project` | `.ai/PROJECT.md` |
| `architecture` | `.ai/ARCHITECTURE.md`, `.ai/DECISIONS.md` |
| `requirements` | `.ai/REQUIREMENTS.md` |
| `api-or-schema` | `docs/API_CONTRACT.md`, `.ai/NAMING_CONVENTIONS.md`, `docs/DATABASE.md`, owning feature doc; add `contracts/openapi.json` when it exists and implemented endpoint detail matters |
| `registration` | `docs/REGISTRATION_VERIFICATION.md`, `docs/USER_ROLES.md` |
| `auth-rbac` | `docs/USER_ROLES.md`, `docs/SECURITY.md` |
| `appointments` | `docs/APPOINTMENT_SCHEDULING.md`; add `docs/REAL_TIME_MESSAGING.md` only for online-session integration |
| `messaging` | `docs/REAL_TIME_MESSAGING.md`; add `docs/APPOINTMENT_SCHEDULING.md` only for appointment-linked conversations |
| `sos` | `docs/SOS_TRIAGE.md`; add `AI_EMOTIONAL_BASELINE.md` only for cue integration |
| `expression-cue` | `docs/AI_EMOTIONAL_BASELINE.md` |
| `wellness-resources` | `docs/WELLNESS_RESOURCE_DISCOVERY.md` |
| `virtual-assistant` | `docs/VIRTUAL_GUIDANCE_ASSISTANT.md` |
| `content-operations` | `docs/CONTENT_MANAGEMENT.md`, `docs/COUNSELOR_DASHBOARD.md`, `docs/USER_ROLES.md` |
| `security` | `docs/SECURITY.md`, owning feature doc |
| `cross-feature-workflow` | `docs/WORKFLOWS.md`, involved feature docs only |
| `whole-system-review` | `.ai/PROJECT.md`, `.ai/ARCHITECTURE.md`, `.ai/DECISIONS.md`, `docs/SYSTEM_OVERVIEW.md`, then targeted docs |

Conflict order is defined once in `RULES.md`. Correct stale prose when an approved decision supersedes it.
