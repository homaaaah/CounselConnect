# CounselConnect — Cross-Feature Workflows

Detail lives in feature docs; this file only joins modules.

## Authentication session

```text
verify Student email/student number or staff email + password
→ create revocable hashed opaque session in MySQL
→ secure HttpOnly web cookie + CSRF protection
→ one-hour idle / 12-hour absolute limit
→ logout, reset, restriction, disable, or expiry → revoke/deny
```

A five-minute warning permits explicit continuation. Genuine CounselConnect actions renew idle time; background polling and WebSocket heartbeats do not. `Remember Me` is excluded from v1.

## Account lifecycle

```text
register + current COR → automated screening (format + OCR + barcode)
→ register returns a one-time X-COR-Token (no auto sign-in)
   ↘ technical FAILED → NO account created; retry later (`503 SCREENING_FAILED`)
→ AWAITING_CONFIRMATION / NEEDS_RESUBMISSION → Student confirms or requests an edit (Superadmin approves) → ACTIVE until valid_until
   ↘ Re-upload COR (new COR, token rotated) or Reject account (deletes the account; email/student number freed)
expired validity → new current COR → screening → confirm → new valid_until → ACTIVE
closing the modal loses the token → Student signs in → session-authorized #registration path
Superadmin recovery resets a stuck non-active Student to PENDING_VERIFICATION.
```

## Appointment to counseling

```text
Counselor configures campus Guidance Office location
→ creates concrete slot with ONLINE / FACE_TO_FACE / BOTH support
→ Student selects slot and compatible ONLINE / FACE_TO_FACE mode
→ PENDING request → Counselor confirms/rejects
→ ONLINE: at scheduled start, create/reuse dedicated APPOINTMENT conversation
→ FACE_TO_FACE: display saved campus Guidance Office location snapshot
→ COMPLETED / NO_SHOW / CANCELLED
```

## Live interaction

```text
authorize Student↔Counselor pair and GENERAL / APPOINTMENT / SOS purpose
→ optional local expression scan → session-only cue
→ text messages → close → 30 days → purge message bodies
```

An `APPOINTMENT` conversation requires a confirmed online appointment at its scheduled start. Appointment and conversation participants must match. General Live Chat remains independent.

## SOS

```text
five answers → approved rules → bounded result or OPEN case
→ generic alert to authenticated, connected, recently confirmed AVAILABLE Counselor
→ Counselor response / approved emergency-contact fallback
→ RESPONDED → CLOSED
```

Counselor `AVAILABLE` / `BUSY` / `UNAVAILABLE` presence is separate from login. Logout, session expiry, or lost connection makes the Counselor unavailable. Expression cue runs beside this flow and never enters the rule calculation.

## Resources and assistant

```text
allowlisted metadata or Counselor manual content
→ validate/categorize/review → PUBLISHED library
→ Student search and bounded assistant recommendations
```
