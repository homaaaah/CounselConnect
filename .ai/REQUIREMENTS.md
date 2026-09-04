# CounselConnect — Requirements

Use IDs in tasks/tests. Owning feature docs contain detail.

| ID | Requirement |
|---|---|
| FR-REG-01 | Student registers with account/academic data, personal email, and current COR; account starts `PENDING_VERIFICATION`. |
| FR-REG-02 | Assigned Guidance Staff or Counselor decides `APPROVED`, `NEEDS_RESUBMISSION`, or `REJECTED`; seven-day timeout becomes `EXPIRED`. |
| FR-REG-03 | Approval sets `ACTIVE` and `valid_until`; expired enrollment locks normal Student features until renewed. |
| FR-AUTH-01 | Authentication and backend role/ownership authorization protect every non-public operation. |
| FR-APPT-01 | Counselor creates concrete availability; Student requests a slot; Counselor confirms/rejects and records outcomes. |
| FR-APPT-02 | Counselor assigns `ONLINE`, `FACE_TO_FACE`, or `BOTH` support to each concrete slot; Student selects `ONLINE` or `FACE_TO_FACE` only when compatible with the slot. |
| FR-APPT-03 | Counselor alone configures each campus Guidance Office location. Face-to-face-capable availability requires that location, and a face-to-face appointment stores it as a booking-time snapshot. |
| FR-APPT-04 | A confirmed online appointment provides one dedicated appointment-linked Live Chat when its scheduled start is reached. |
| FR-MSG-01 | An authorized Student and Counselor exchange secure real-time text in a one-to-one conversation. |
| FR-MSG-02 | The system distinguishes `GENERAL`, `APPOINTMENT`, and `SOS` conversations and enforces their source-specific authorization and linkage rules. |
| FR-SOS-01 | SOS validates five approved answers, applies approved rules, creates/alerts cases when required, and shows approved fallback contacts under the final availability rule. |
| FR-CUE-01 | Live Chat/SOS may offer an optional local ~3-second expression scan producing session-only read-only Counselor context. |
| FR-RES-01 | Students search `PUBLISHED` internal/external wellness resources by text/category. |
| FR-RES-02 | Automated discovery retrieves bounded metadata from allowlisted sources, normalizes/deduplicates it, and requires Counselor review. |
| FR-RES-03 | Counselor creates manual external links, internal articles, or controlled multi-file resources and assigns multiple categories. |
| FR-AST-01 | Assistant returns bounded navigation, approved FAQ, or published-resource responses only. |
| FR-OPS-01 | Counselor manages authorized accounts/Guidance Staff, academic corrections, CMS/FAQs, announcements, emergency contacts, resources, campus Guidance Office locations, and operational audit views. |
| FR-STAFF-01 | Guidance Staff accesses only assigned enrollment-verification work. |
| FR-MOB-01 | Core workflows support desktop and Capacitor-oriented mobile use. |
| PR-REG-01 | COR files are private temporary artifacts, never MySQL blobs/public URLs; delete after decision/expiry and track cleanup failures. |
| PR-CUE-01 | Raw camera media and embeddings never leave the device or persist; cue never changes SOS results. |
| PR-MSG-01 | Purge message bodies 30 days after conversation closure; do not create recordings/transcripts/summaries. |
| PR-RES-01 | Do not mirror full third-party articles or blindly host publisher images. |
| SEC-01 | Validate untrusted input and use least privilege, safe queries, externalized secrets, and sensitive-data-safe logging. |
| SAFE-01 | No diagnosis, clinical certainty, or medical recommendation. |
| NFR-01 | Maintainable/testable modular-monolith code appropriate for a four-person team. |
| NFR-02 | Store/transmit only necessary data; use UTC and explicit failure states. |

Missing behavior is an open requirement, not permission to invent it.
