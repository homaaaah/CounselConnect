# CounselConnect — SOS Triage and Response

## Contract

An authenticated Student answers five approved questions. The backend validates completeness and applies the approved **rule-based** alert condition only. It returns a bounded result or creates an `OPEN` case and alerts an authorized Counselor.

Counselor claims/responds (`RESPONDED`), may link an authorized messaging conversation, then closes the case (`CLOSED`). If Counselor support is unavailable under the final rule, show ordered active emergency contacts.

## Expression-cue separation

Optional local facial-expression output is session-only Counselor context. It must not enter answer validation, weights, thresholds, urgency result, alert creation, availability, or fallback logic. Identical answers must always produce the same result regardless of cue.

## Safety/security

- Do not diagnose or describe rule output as clinical certainty.
- Enforce Student ownership and Counselor case scope; prevent duplicate cases/alerts from retries.
- Collect/retain only approved workflow data; Guidance Staff has no access.

## Required tests

Incomplete/invalid answers; each rule boundary; duplicate submission; ownership/role access; available/unavailable fallback; `OPEN→RESPONDED→CLOSED`; SOS result invariant across all cue values/absence.

## Pending

Exact instrument/version, rule thresholds, availability/fallback timing, and SOS retention.
