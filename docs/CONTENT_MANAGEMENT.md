# CounselConnect — Content Management

Counselor manages designated structured content; Guidance Staff has no access.

## Content types

- landing/Guidance Office/service information and approved FAQs,
- announcements,
- structured emergency contacts: name, number, description, display order, active state.

Ordinary content becomes current after validated save. Announcements use manual publish/unpublish. V1 has no drafts, revision history, rollback, scheduling, or arbitrary rich HTML.

CMS cannot alter code, routes, business logic, roles/permissions, server/database configuration, secrets, or AI instructions. Validate length/type and sanitize rendering. Emergency contacts must be structured records used by SOS fallback.

## Required tests

Counselor-only authorization; field constraints; injection/safe rendering; immediate ordinary-content update; announcement publish/unpublish; ordered active contacts; content changes cannot alter application behavior.
