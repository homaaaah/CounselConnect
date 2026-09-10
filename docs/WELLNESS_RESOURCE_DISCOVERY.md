# CounselConnect — Wellness Resources

## Automated discovery

```text
allowlisted source → RSS/Atom/structured metadata first
→ approved bounded scraping fallback → validate/normalize/canonicalize/dedupe
→ PENDING → Counselor edit/categorize/approve/reject
→ PUBLISHED card → canonical publisher link
```

Store only bounded card metadata: title, summary/excerpt, source, canonical URL, publication/discovery/review fields, categories, and safely permitted image reference. Never mirror a third-party full article or bypass paywalls/auth/anti-bot controls. Enforce domain/redirect checks, timeouts, size limits, sanitization, and deduplication.

## Manual resources

Counselor may create:

- external link with validated metadata/URL,
- internal Guidance Office article,
- internal resource with one or more controlled durable attachments.

A resource may have multiple categories. Tags are deferred. Manual-resource publication/review policy is pending.

## Publication/access

Statuses: `PENDING`, `PUBLISHED`, `REJECTED`, `DISABLED`. Only `PUBLISHED` resources appear to Students or the assistant. Counselor may later disable a publication. Guidance Staff has no access.

## Required tests

Allowlist/redirect/SSRF safety; malformed/oversized fetch; canonical dedupe; pending exclusion; review/status transitions; no full-body persistence; controlled attachment authorization; multiple categories; safe missing image.

## Pending

Final source allowlist, fetch cadence, manual publication rule, attachment limits, and image/license policy.
