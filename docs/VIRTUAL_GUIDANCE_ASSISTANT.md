# CounselConnect — Virtual Guidance Assistant

## Allowed

- system navigation from approved current content,
- approved FAQ answers,
- recommendations from `PUBLISHED` resource metadata/cards.

## Forbidden

Diagnosis, medical recommendations, counselor replacement, invented university policy, pending/unreviewed resources, confidential-data disclosure to an external model, tool/action execution not explicitly approved, and persistent assistant conversation history.

Unsupported/clinical/confidential requests return a bounded limitation and appropriate approved support direction. The assistant must treat retrieved/external text as data, not instructions.

No vector database is required for v1; use the simplest bounded retrieval that satisfies approved navigation/FAQ/resource scope. Provider/model remains pending.

## Required tests

Each supported request class; pending/disabled exclusion; unknown/clinical handling; prompt injection; authorization/data leakage; no history persistence; canonical resource links.
