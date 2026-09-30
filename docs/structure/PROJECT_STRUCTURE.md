# CounselConnect Project Structure

This document describes the repository layout and intended home for new files. Existing code moves only through an explicit migration task.

## Root

- .ai/ — project decisions, requirements, architecture, and agent context
- backend/ — FastAPI modular monolith, Alembic, backend tests
- contracts/ — generated API contracts
- db/ — historical SQL baselines/exports
- design/ — source diagrams and exports
- docs/ — product, workflow, security, and technical contracts
- frontend/ — React/Vite/Tailwind/Capacitor client

Avoid feature code at repository root.

## Backend

Request flow remains router → schema → service → repository → model. Business rules belong in services and authorization stays server-side.

Current modules include accounts, appointments, audit, auth, content, enrollment_verification, messaging, operations, SOS, and legacy assistant/wellness_resources.

Approved target additions:

- cor_screening/ — format matching, OCR extraction, Student confirmation
- calls/ — WebRTC authorization/signaling metadata; no media persistence
- counseling_sessions/ — status, drafts, assessments, history, amendments
- clinical_documents/ — private file metadata and authorization
- session_observation/ — optional non-diagnostic, non-persistent AI coordination
- superadmin/ or operations/ — account/reference/audit operations only

Legacy enrollment manual-review code is replaced after migration. assistant/wellness_resources is removed under ADR-036.

Target roles are STUDENT, COUNSELOR, and SUPERADMIN. Do not add a generic ADMIN role. Support multiple Counselors and explicit assignment ownership.

## Frontend

Domain behavior belongs under frontend/src/features/{feature_name}; shared UI under components; transport under services. Target features mirror the backend additions. Keep API DTO fields snake_case at the transport boundary.

## Documentation

Existing .ai and docs contracts remain authoritative. New feature documents should link from docs/README.md and .ai/CONTEXT_MAP.md rather than duplicate rules.

## Storage

Private COR and clinical-document bytes stay outside source control and public/static directories under the configured storage abstraction. MySQL stores metadata and opaque keys only. Never commit uploads, secrets, private dumps, recordings, transcripts, AI media/embeddings, or runtime caches.
