# CounselConnect — Wellness Resource Feature Removal

**Status: removed from approved target scope (ADR-036).**

Decommission:

- automated RSS/metadata discovery and scraping,
- Counselor review/publication queues,
- manual/internal/external Wellness Resources,
- resource files, categories, and Student views,
- discovery jobs and allowlists,
- resource-based assistant retrieval,
- related routes, UI, tests, seeds, and tables.

## Safe removal order

1. Stop new discovery/publication writes.
2. Remove or disable UI and API exposure.
3. Decide whether data needs export; production deletion needs an approved plan.
4. Remove jobs, services, tests, and configuration.
5. Drop resource-only tables in a reversible Alembic migration after dependency checks.
6. Regenerate OpenAPI and update references.

This is a removal record, not a contract for new resource work.
