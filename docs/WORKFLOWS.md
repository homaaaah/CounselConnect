# CounselConnect — Cross-Feature Workflows

Detail lives in feature docs; this file only joins modules.

## Account lifecycle

```text
register + current COR → pending review → approve → ACTIVE until valid_until
                                      ↘ resubmit/reject/7-day expiry → restricted access
expired validity → latest COR → review → new valid_until → ACTIVE
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
→ Counselor response / approved emergency-contact fallback
→ RESPONDED → CLOSED
```

Expression cue runs beside this flow and never enters the rule calculation.

## Resources and assistant

```text
allowlisted metadata or Counselor manual content
→ validate/categorize/review → PUBLISHED library
→ Student search and bounded assistant recommendations
```
