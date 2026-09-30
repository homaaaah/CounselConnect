# CounselConnect — Counseling Session Records

**Status: approved target; planned implementation.**

Each appointment has a counseling-session record that tracks SCHEDULED, IN_PROGRESS, ENDED, DOCUMENTATION_PENDING, and FINALIZED.

## Counselor workflow

1. Assigned Counselor starts/ends the scheduled session.
2. Counselor writes private draft notes during or after the session.
3. Counselor creates and reviews a structured assessment.
4. Finalizing makes the assessment immutable and visible read-only to the Student.
5. A future assigned Counselor session may show relevant prior finalized assessments and amendments for continuity.

Drafts are visible only to the assigned Counselor. They are never visible to the Student or Superadmin.

## Corrections

A Student may request a correction to their finalized assessment. Superadmin administers routing/status only. The assigned Counselor accepts/rejects the request and, when needed, authors an append-only amendment. Never overwrite or backdate finalized clinical content.

## Audit and privacy

Audit status changes, finalization, correction decisions, and amendments using record IDs and actors only. Do not copy note/assessment content into audit logs. Retention remains pending ADR-P12.
