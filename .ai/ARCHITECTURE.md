# CounselConnect — Architecture

## Shape

```text
JavaScript (React)/Vite/Tailwind (+ Capacitor)
          │ HTTPS; web cookie session
       FastAPI modular monolith
          │ routes → schemas → services → repositories
 SQLAlchemy 2.0 + PyMySQL + Alembic
          │
      MySQL 8.4 LTS
```

Routes own transport, schemas validate contracts, services own authorization/business rules, repositories own persistence. Web authentication uses a secure HttpOnly opaque-session cookie with CSRF protection; real-time messaging transport and Capacitor credential transport remain separately pending. Do not duplicate business rules in React.

## Modules

`auth`, `accounts`, `enrollment_verification`, `appointments`, `messaging`, `sos`, `wellness_resources`, `assistant`, `content`, `operations`, `audit`. Exact folders may follow the codebase, but cross-module access goes through service contracts.

The `appointments` module may request creation or reuse of an appointment-linked conversation through the `messaging` service. It must not directly create message records or bypass messaging authorization. The messaging service returns the conversation reference; the appointments service persists the unique link.

## Non-MySQL storage

- Temporary private COR store: maximum seven-day pending lifetime; delete after decision/expiry.
- Controlled durable resource-file store: internal Counselor-authored attachments only.
- Local device memory: optional facial-expression scan and session cue; never durable.

## Critical flows

- Authentication: verify identifier/password → create hashed opaque `user_sessions` record → secure web cookie → authorize every protected request → revoke on logout/reset/restriction/disable; one-hour idle and 12-hour absolute limits apply.
- Counselor SOS presence: explicit `AVAILABLE`/`BUSY`/`UNAVAILABLE` + valid connection/recent confirmation; background generic alert; logout/expiry/disconnect → unavailable.
- Registration: validate → pending account + temporary COR → Staff/Counselor decision → set `valid_until`/state → delete COR.
- Appointment availability: Counselor selects campus, concrete time, and `ONLINE`/`FACE_TO_FACE`/`BOTH`; face-to-face-capable slots require the Counselor-managed campus Guidance Office location.
- Appointment booking: validate active Student, slot availability, and mode compatibility → reserve slot and create `PENDING` appointment → copy the campus location for face-to-face → Counselor decision/outcome.
- Online appointment: confirmed `ONLINE` appointment reaches scheduled start → appointments service requests an `APPOINTMENT` conversation → messaging validates matching participants → appointments stores the unique conversation reference.
- Messaging: authorize Student/Counselor pair and conversation type → text exchange → close → purge bodies after 30 days.
- SOS: validate five-question instrument → approved rules → case/alert/fallback; expression cue is a separate context path.
- Discovery: allowlisted source → bounded metadata → normalize/dedupe → `PENDING` → Counselor review → published card/canonical link.

## Non-goals

No microservices, distributed event bus, identity facial recognition, biometric database, cloud facial analysis, autonomous clinical engine, persistent assistant history, or vector database unless a new approved decision requires one.
