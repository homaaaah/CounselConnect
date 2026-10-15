# CounselConnect — SOS Triage and Response

An authenticated Student answers five approved questions. The backend validates completeness and applies only the approved deterministic rule. It returns a bounded result or creates an OPEN case and alerts an authorized Counselor.

A Counselor responds (RESPONDED), may link an authorized SOS conversation, then closes the case (CLOSED). If no Counselor is available under the approved rule, show ordered active emergency contacts.

## Availability and alerts

Availability is separate from authentication: AVAILABLE, BUSY, or UNAVAILABLE plus a valid connection and recent confirmation. Logout, session expiry, or disconnect makes the Counselor unavailable. Background browser/device alerts are generic and expose no Student identity, answers, urgency, or case details. Heartbeats never renew authentication.

## AI separation

AI-assisted session observation never enters SOS answer validation, thresholds, urgency, alert creation, availability, or fallback. Identical answers always produce the same result.

## Security/tests

Enforce Student ownership and Counselor case scope; Superadmin sees operational audit metadata only, not answers by default. Test incomplete/invalid answers, every rule boundary, retries, role/ownership, availability/fallback, state transitions, generic alerts, session expiry, and identical results with/without AI.

Exact questions, thresholds, office hours/response window, fallback, and privacy notice remain pending ADR-P03.
