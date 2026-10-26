# Registration Information Corrections and Users Management

## Status and scope

**AGREED target contract, Task 2, 2026-10-25; implementation is incremental as recorded below.** The user approved the bounded pending-correction COR retention exception on this date. Existing implementation remains described in `REGISTRATION_VERIFICATION.md` and the current routes in `API_CONTRACT.md`. Generated OpenAPI continues to describe implemented behavior only. This contract supersedes conflicting portions of ADR-029/030/032 for these two modules; it does not change clinical assessment corrections.

Extend `cor_screening`, `profile_change`, `accounts`, and `auth`. Reuse the existing registration form, field editor, account hooks, navigation, session/CSRF controls, private storage, cleanup loop, audit service, and list envelope. No new dependency, worker, notification system, general profile editor, role reassignment, staff invitation, or hard-delete operation is required. The user-approved 2026-10-26 Counselor account extension below narrowly adds Counselor creation and names/email editing by Superadmin.

Initial correction fields remain names, year level, and section. Student Number corrections, email changes, campus/program corrections, and academic-period corrections are outside this release. Student Number uniqueness tests cover existing registration/confirmation and fresh evidence identity matching; this module does not introduce a proposed login identifier.

## Implemented schema increment (Task 3.1)

Migration `20261025_correction_context` extends `20261024_weekly_sched_softdel`. The ORM and migration now provide nullable `submission_version`, predecessor/root references, `extracted_values_json`, `registered_values_json`, the baseline `registered_cor_screening_id`, and exact evidence ID/digest/upload/expiry metadata. A first version has a null root pointer and uses its own request ID as the logical root; later versions reference that ID. Unique predecessor and root/version constraints prevent duplicate successors and duplicate version numbers. File identity has no live-file FK so cleanup can delete temporary metadata without erasing historical identity.

Historical rows retain unknown context: no metadata backfill or fabricated requests/versions/decisions. Initial submission now populates new context as described in Task 4.2 below; retention now follows Task 4.3 below. The API supports `RETURNED` for system evidence transitions; manual return/resubmission remains later work. Nullable context preserves registration rows created before snapshot recording was implemented. Downgrade refuses to discard any populated context or returned decision; stop application writers before migration/rollback. Task 4.2 records immutable snapshots and validates ownership/context; Task 4.4 adds the one-pending-per-Student database guard described below. Task 3.2 adds their schema foundations as described below.

## Implemented schema increment (Task 3.2)

Migration `20261025_account_screening_scope` extends `20261025_correction_context`. `users.is_deactivated` is non-null with a database/ORM default of false and a 0/1 check. `cor_screenings.purpose` is non-null with a database/ORM default of `REGISTRATION` and allowed values `REGISTRATION`/`CORRECTION`. Existing records receive these defaults without changes to account eligibility, screening status, extraction, or decision metadata. No deactivation or correction-only screening is created by migration.

Upgrade supports retry after partial additive DDL. Downgrade preflights both tables and refuses to drop fields if any deactivated account or non-registration screening exists; it cannot silently remove a restriction or reinterpret review evidence as enrollment evidence. Stop application writers before migration/rollback.

These are schema foundations only. Existing APIs still create registration-purpose screenings and expose the existing response shapes. Authentication does not yet enforce the new deactivation flag, and existing enrollment/cleanup queries do not yet isolate correction-purpose rows. No endpoint sets either non-default value yet; workflow isolation must land before any correction-only screening creation, and deactivation enforcement must land with its action endpoints. Task 3.2 itself made no retention change; Task 4.3 below implements the bounded exception. The one-pending-per-Student database guard remains coordinated with versioned submission writes in Task 4.

## Implemented normalization increment (Task 4.1)

Supported names/section normalize whitespace before request-length validation; blank middle names become null and year level requires an actual JSON integer in the existing 1?10 range. `profile_change/normalization.py` shares canonical field validation across COR confirmation/request submission and existing review validation. Backend casefold comparison controls actual differences. No-change submission activates with canonical extracted spelling and creates no empty request. A missing required extraction is rejected rather than replaced by Student-proposed information.

Adding a middle name to null extraction now creates a pending proposal and leaves the registered/extracted middle name null; clearing an extracted middle name also remains pending. Plain confirm cannot bypass review for either. Both token and session submission use the same core implementation. A token-authorized addition, successful subsequent login, and authorized appointments access while pending are covered through the API in MySQL tests.

The shared field editor now supports years 1?10 and identifies additions against null extraction. Test vectors in `contracts/registration-normalization-cases.json` cover null/blank, whitespace, case, punctuation, accents, years, and Unicode casefold. The client intentionally keeps its simple lowercase preview: the server remains authoritative for Unicode cases such as Stra?e/STRASSE. React/API tests verify successful activation with no pending message when the server returns no request. No new dependency or Unicode mapping table is introduced.

Rows written before Task 4.2 still have unknown context; no history is reconstructed. Initial snapshot recording is implemented below; Task 4.5 adds Student status reads below; hardened review remains later work; Task 4.4 adds pending uniqueness, and retention is implemented in Task 4.3. No migration or API shape changes are required for Task 4.1.

## Implemented initial submission context (Task 4.2)

Initial registration/renewal correction submission now writes `submission_version = 1`, with null predecessor/root references (the row's own ID is the logical root). Ownership uses the authenticated/resolved Student's stable user ID; mismatched owners receive `SCREENING_NOT_FOUND`, and non-registration-purpose screenings cannot establish this registration context. Existing approved/rejected/legacy requests are not modified or backfilled.

Before activation modifies the screening row, capture the structured extraction's names, Student Number, campus/program IDs, year, section, academic period, and extracted validity date (ISO date or null). Preserve explicit nulls and original structured spelling/whitespace in this snapshot, including unmapped references. After activation, record the canonical registered baseline established by that same confirmation, including selected active reference IDs and its actual enrollment validity date. On renewal this is the newly confirmed enrollment baseline, not a reconstructed earlier registered value. The exact confirmation screening ID is retained separately as baseline context. Requested fields remain in the existing requested columns and never become the registered baseline before approval.

A changed submission locks and requires an unexpired `PENDING`-cleanup file-metadata row attached to its exact screening. Copy only file ID, SHA-256 digest, original upload time and original expiry into the request; no file bytes, storage path/key, filename, token, raw OCR/barcode, or arbitrary validation payload enters either snapshot. Missing/expired/failed-cleanup metadata returns `409 COR_EVIDENCE_UNAVAILABLE` before activation or request creation; no-change confirmation behavior is preserved. Actual byte availability/integrity checks at review remain future work, so metadata capture does not claim that evidence remains viewable.

Activation, request/snapshots, and submission audit events commit together. Audit metadata is limited to account/request status and submission version, with the existing actor/target IDs and UTC timestamps; no proposed/extracted values or file digest enters general audit metadata. An audit failure rolls back activation/request/token changes and does not delete the COR. Snapshots are independent stored JSON values: later profile/extraction changes do not rewrite them, and repeated submission cannot edit the existing submitted version.

No API response fields or migration change in this increment; the internal snapshots/hash/file identity are excluded from the existing response DTO. Task 4.2 originally preserved post-activation deletion; Task 4.3 below now implements bounded pending-review retention. Review must not be described as complete or evidence as available merely because a reference is stored. Task 4.4 below implements pending uniqueness at the database level; Task 4.5 adds Student-owned reads below; resubmission and hardened review remain target work.

## Implemented bounded evidence retention (Task 4.3)

The existing COR cleanup flow now retains only the exact file attached to a versioned `PENDING` correction after successful confirmation. It checks the owner/screening relationship, file ID, metadata digest, original upload time and expiry. Retention ends at the earliest stored request expiry, its original upload time plus seven days, the file expiry, replacement, or a terminal decision. Neither confirmation nor cleanup extends deadlines. No-change confirmation still deletes immediately. Unknown legacy context never grants a retention exception.

At expiry the worker marks the version `RETURNED` with `COR_EVIDENCE_EXPIRED`, null reviewer, review timestamp, and safe system audit metadata. Missing/failed-cleanup/inconsistent metadata produces `COR_EVIDENCE_UNAVAILABLE`; replaced/non-current evidence produces `SUPERSEDED_BY_NEW_COR`. Expiry candidates include overdue request references even if temporary file metadata has disappeared. No registered field, account status or enrollment validity is changed by these correction transitions. An approval of a versioned request independently denies expired/missing stored deadlines before the worker runs; full review byte-integrity/stale-data/version hardening remains Task 6.

Cleanup locks the Student, screening and pending requests before file metadata, commits a return and its audit before deleting bytes, and re-locks/rechecks current state after that commit. Audit failure leaves bytes untouched for retry. Deletion failure retains `cleanup_state=FAILED` and the existing worker retries; safe logs contain outcome codes and internal IDs only. The existing approve/reject routes invoke cleanup after their decision/audit commit, so a terminal decision releases the COR immediately. Manual rejection keeps the existing `REJECTED` semantics until Task 7; no manual return/resubmission endpoint is added here.

A new enrollment upload supersedes versioned pending corrections as `RETURNED`, audits the system reason and deletes their old COR after the replacement transaction commits. The new unconfirmed upload remains subject to ordinary screening/confirmation restrictions. Legacy requests keep existing rejection semantics and unknown history. Original extraction/baseline/evidence snapshots remain unchanged after deletion or replacement. No historical COR becomes viewable again.

The upload notices disclose the pending-correction exception, decision/replacement deletion and original seven-day deadline. OpenAPI is regenerated to include the `RETURNED` response status; no route or private COR download is added. The same lifespan cleanup loop is used, with no new worker, timer, table, notification mechanism, or migration. Cleanup cannot run while all application/cleanup processes are stopped; failures remain detectable/retryable under the existing operational policy.

## Implemented pending-owner database guard (Task 4.4)

Migration `20261025_pending_correction` extends `20261025_account_screening_scope`. A virtual generated `pending_student_user_id` derives the stable `student_user_id` only when status is `PENDING`, otherwise null. Unique key `uq_profile_change_requests_pending_student` enforces at most one pending row per Student across all screenings and versions, including legacy rows. Multiple terminal rows remain allowed. This is a constraint-only derived value, not an editable ownership field, a new identity, or a historical registered-value backfill. It is not eagerly loaded by the ORM or exposed in response DTOs.

The existing Student-row lock and friendly pre-check remain. MySQL duplicate-key failure for this specific guard during creation rolls the transaction back and returns the same safe `409 CHANGE_REQUEST_PENDING`, without SQL, key names, duplicate identifiers or proposed values in the error. Other database failures are not mislabeled as pending conflicts. Status transitions automatically release the unique slot; application/cleanup code needs no separate flag update. The existing foreign-key actions remain unchanged; no trigger, lock table, dependency, or worker is added.

Upgrade preflights duplicate pending owners before DDL. If ambiguity exists, it stops without deleting, returning, approving, relabeling or choosing a request. Resolve the actual records through an authorized review before retrying; this migration performs no such review. Valid upgrades and partial-upgrade retries preserve requests, snapshots, timestamps, statuses, decisions and unknown historical metadata. Downgrade removes only the unique key and derived column, preserving business data. Stop application writers before upgrade/downgrade because MySQL DDL commits independently. Migration verification uses disposable schemas; the application database has not been migrated by this task.

Tests cover schema/foreign-key/data preservation, retry after a partially added column, downgrade/re-upgrade, duplicate-preflight refusal, same/different-screening duplicates, completed-state slot release, attempted null override, simultaneous direct inserts with one winner, and safe service conflict mapping. Task 4.4 itself added no read workflow; Task 4.5 below adds Student reads, while the remaining review/version workflow is still target work.

## Implemented Student status reads (Task 4.5)

`GET /profile-change-requests` now accepts a Student session and returns only that stable account's requests. `GET /profile-change-requests/{change_request_id}` returns the same safe item for an owning Student; another owner's or a missing ID returns identical `404 CHANGE_REQUEST_NOT_FOUND`. These are session-only reads: a COR token does not authorize them. Deactivated Students receive `403 ACCOUNT_DEACTIVATED`; Counselors and Guidance Staff receive `403 FORBIDDEN_ROLE`. Pending/expired Students may read their own account correction outcomes without unlocking ordinary features. Reads do not change correction status, snapshots, registered fields, account eligibility, evidence deadlines or audit history; normal session activity controls still apply.

Student lists use SQL owner filtering/counting and pagination (page 1, size 20 default, max 100), newest submission then ID descending. `status` is optional and restricted to the four supported statuses; omission lists all statuses. Invalid status/page values return safe `422 VALIDATION_ERROR`. A query-supplied owner never overrides the authenticated owner. Empty/out-of-range pages return an empty items array with the correct owned total.

The Student list/detail item is intentionally narrower than the planned full Superadmin review detail:

```text
{
  change_request: {
    change_request_id, student_user_id, cor_screening_id,
    submission_version, previous_change_request_id, root_change_request_id,
    status, requested_first_name, requested_middle_name, requested_last_name,
    requested_year_level, requested_section, created_at, reviewed_at, decision_reason
  },
  current_first_name, current_middle_name, current_last_name,
  current_year_level, current_section
  registered_values_at_submission: {first_name,middle_name,last_name,year_level,section} | null
  changed_fields: [supported field names] | null
}
```

Current values come from the account/profile, not extraction or unapproved proposals. Missing current profile values remain null. The comparison baseline is an allowlisted projection of the stored snapshot; unknown, incomplete or invalid legacy context remains null, with `changed_fields: null` rather than an invented historical diff. Known differences use the same normalization as submission, so an approved outcome still identifies its originally changed fields even after current values match the approved proposal. Legacy version numbers remain null. Created/review timestamps use UTC `Z`.

Student responses omit reviewer IDs, the pending-owner guard, private file identity/hash/paths, raw snapshot JSON, tokens, arbitrary extra JSON keys, audit feeds and clinical content. Successful read responses are `Cache-Control: no-store`. There is no generic request-update operation; status reads do not permit rewriting a submitted proposal or deciding it.

The existing Superadmin queue keeps its item shape and permissions; its frontend already requests `status=PENDING`. Omitted status now means all statuses consistently with the agreed contract. Its in-memory pagination remains until Task 5. The new status-detail GET is Student-only in this increment; Superadmin full detail/private COR reads remain Task 5. Lineage-specific history filtering, manual return/resubmission, and Student UI integration remain later work. No migration, frontend UI or notification mechanism is added here. OpenAPI records the two role-specific list response DTOs and the Student detail operation.

## Implemented submission whitelist (Task 4.6)

Both `POST /cor-screenings/confirm` and `POST /cor-screenings/request-edit` reject unknown JSON properties with `422 VALIDATION_ERROR`. Their shared DTO accepts only `student_number`, `first_name`, `middle_name`, `last_name`, `campus_id`, `program_id`, `year_level`, `section`, and optional `academic_period`; existing required-field and normalization rules remain. The presence of baseline/context fields does not authorize changing protected identity, mapped references or academic period. Owner, screening, role, reviewer, status, version and evidence overrides are unsupported inputs rather than silently ignored properties.

Validation uses the existing safe envelope: field locations/error types and a generic message, without submitted values or raw validator context. Ownership still comes from the resolved one-time COR token or authenticated Student session. Session submissions require the existing CSRF header; a present invalid COR token fails closed instead of falling back to a valid session. This increment adds no route, migration, retention rule or permission.

## Implemented Superadmin queue increment (Task 5.1)

The Superadmin branch of `GET /profile-change-requests` now counts, filters and paginates in SQL with the same validated page/status parameters and list envelope. Omitted status includes all statuses; sort order is newest submission timestamp then request ID descending. Existing request/Student/current-value fields remain, with nullable `changed_fields` added from the immutable allowlisted submission baseline. Unknown, incomplete or invalid legacy baseline produces null, never a comparison fabricated from current profile values. Missing current Student profile fields remain null without dropping a request. Request timestamps serialize as UTC `Z`; successful queue responses remain `no-store`.

The existing shared Superadmin review guard also denies operationally deactivated accounts with `403 ACCOUNT_DEACTIVATED`, covering the queue and existing decisions. Active role enforcement remains authoritative; this is a local review guard, not global deactivation/session enforcement. Student reads retain their SQL owner restriction and safe response. The queue exposes no raw snapshots, private evidence metadata, storage paths, tokens or clinical data. Superadmin detail, lineage history filtering and private COR retrieval remain subsequent Task 5 increments; full safe approval remains Task 6.

## Implemented lineage list increment (Task 5.2a)

`GET /profile-change-requests` accepts optional `root_change_request_id` (positive unsigned BIGINT ID). Role/deactivation checks run first. An owning Student or active non-deactivated Superadmin must resolve an actual root before history counting/pagination. Another Student's root, a missing root, or a descendant supplied as the root returns the same `404 CHANGE_REQUEST_NOT_FOUND`. A root has no predecessor or root pointer; legacy standalone requests remain valid roots with unknown version metadata.

History includes that root and explicitly linked descendants only, with the verified root's stable owner applied in SQL to both counts and pages. Same-owner unrelated corrections and cross-owner links are excluded. Status/page filters, newest timestamp/ID ordering, no-store and role-specific safe projections remain. Superadmin queue/history request metadata now adds nullable `submission_version`, `previous_change_request_id` and `root_change_request_id`; existing submission/decision responses are unchanged. Students retain their safe existing metadata without reviewer IDs. Null legacy versions are never fabricated, including an explicit version-1 successor linked to a legacy root.

This is a read-only history list increment. It creates no versions, decisions, evidence access, audit feed, migration or new route. Superadmin detail and exact private COR availability/retrieval remain subsequent Task 5 increments; manual resubmission remains Task 7.

## Implemented Superadmin structured detail (Task 5.2b)

`GET /profile-change-requests/{change_request_id}` now branches by authenticated role: the owning Student keeps the existing narrow status response; an active non-deactivated Superadmin receives `ReviewProfileChangeRequestDetail`. Other staff remain forbidden and missing requests return safe `404 CHANGE_REQUEST_NOT_FOUND`. Successful responses remain `no-store`, and timestamps use UTC `Z`.

The Superadmin detail includes safe request/version metadata and Student summary; independently validated, allowlisted complete extraction and registered-at-submission snapshots; actual current registered values; editable proposals; nullable changed-field names; and at most the selected version and its immediate predecessor in history. Unknown/incomplete/invalid snapshots remain null. Explicit null extraction is preserved. Known proposals contain only differences from immutable baseline; unknown legacy comparison shows all stored editable proposals with `changed_fields: null`. No historical values are reconstructed from current account or extraction rows. Cross-owner/unrelated predecessor links are excluded, and invalid detail lineage pointers are represented as unknown without modifying stored records. Complete history remains in the owner-checked paginated lineage list.

Current names and profile fields come from the account/profile, with missing profile fields null. Current academic period and validity use the latest confirmed, passed registration-purpose screening by confirmation timestamp/ID, never an unconfirmed upload or correction-only screening; absent confirmed context remains null. These are current reads, not approval/staleness validation.

This increment intentionally omits `evidence` until derived availability and exact private retrieval are implemented in Task 5.3; it makes no preview/availability/approval claim. `can_resubmit` remains false until the actual revision workflow ships. Reads change no proposal, profile, snapshot, account eligibility, evidence deadline, decision or audit history. No private file identifiers/digests/paths, raw JSON, tokens, OCR/barcode payloads, clinical content or arbitrary extra snapshot keys are returned. No new route, migration, retention rule or decision behavior is added.

## Implemented derived evidence availability (Task 5.3a)

Superadmin detail now includes `evidence: {availability, expires_at}`. Availability is derived by an internal COR service after the existing reviewer guard. Terminal requests are `RESOLVED` without private-file reads; pending unknown-version legacy requests are `LEGACY_UNKNOWN` without inferring evidence. Missing/inconsistent identity/upload metadata, wrong owner/purpose, missing bytes, unsafe paths, storage errors or failed cleanup produce `UNAVAILABLE`. Replaced screening/current evidence produces `REPLACED`, without substituting any latest file. Missing metadata does not prevent history/detail reads.

`AVAILABLE` requires a versioned pending request, its exact confirmed/passed registration-purpose screening and owner, its exact captured file ID/digest/upload time, pending cleanup, PDF MIME type, no newer active replacement and actual private PDF bytes with matching signature, size and SHA-256. Read size is bounded by the configured COR limit. The effective deadline is capped by all known original request/upload, screening-upload and exact file deadlines; equality means expired. Expiry is checked again after reading. File/header/digest/size corruption is `CORRUPT`; overdue evidence is `EXPIRED` independently of cleanup. UTC deadlines serialize with `Z`. No file identity/hash, private path/key/name, bytes, raw JSON or storage exception text is exposed.

Availability is a point-in-time informational read, not permission to preview or approve; those operations must independently revalidate current state. Reads perform no cleanup, return, audit insertion, deadline extension or account/profile change. Student reads do not invoke evidence inspection or receive this field. Current checks intentionally support only the existing initial registration-purpose correction flow; correction-only screening isolation still precedes any creation of that future flow. Private PDF retrieval remains Task 5.3b and transactional approval remains Task 6.

## Implemented private COR retrieval (Task 5.3b)

`GET /profile-change-requests/{change_request_id}/cor` now requires a live session and an active, non-deactivated Superadmin. Student, Counselor and Guidance Staff callers receive `403 FORBIDDEN_ROLE` before evidence lookup. Anonymous/COR-token-only callers cannot authenticate this route. Authorized missing requests return `404 CHANGE_REQUEST_NOT_FOUND`.

Retrieval rechecks reviewer eligibility under the reviewer-account lock, then locks the Student, screening and selected request in the existing retention/decision order. Changed owner/screening context is denied. Shared evidence inspection uses current locking reads for registration/file/replacement checks and returns the exact bytes it verifies in one bounded read. Retrieval never relies on an earlier detail availability result and never reopens a mutable path after validation. The response is `application/pdf`, has the fixed inline filename `registration-correction-cor.pdf`, `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`, with no storage metadata or permanent/public URL.

Any non-available evidence returns safe `409 COR_EVIDENCE_UNAVAILABLE`, with only `availability` and UTC `expires_at` details; no PDF bytes, paths, filenames, digest or OS exception text appears in the error. Service-level error responses also use `no-store`. Expiry is independently checked during this retrieval, including after the byte read. Terminal/legacy evidence is never served, even if bytes remain after failed cleanup. Existing detail/history remains readable.

This endpoint performs no correction decision, business-field change, deadline extension, cleanup or document-content audit. Normal authenticated session activity is unchanged. Task 5 review reads are implemented; full transactional evidence/version/baseline/uniqueness approval hardening remains Task 6, and manual return/resubmission remains Task 7. Existing approve/reject routes must still be treated as legacy/partially hardened until those tasks complete.

## Implemented approval version binding (Task 6.1)

`POST /profile-change-requests/{change_request_id}/approve` now requires JSON `{submission_version: integer >= 1}`. Missing/null/coerced/boolean/nonpositive versions and extra properties (including proposal, owner, status or reviewer overrides) return safe `422 VALIDATION_ERROR`. The service also requires an explicit strict version, so internal callers cannot bypass the binding with null or a coerced scalar. Successful responses keep their existing shape and now include `Cache-Control: no-store`.

After existing role/deactivation checks and the Student/screening/request locks, approval first requires pending state. Unknown legacy submission versions cannot be invented for approval (`409 COR_EVIDENCE_UNAVAILABLE`). A different recorded version returns `409 CHANGE_REQUEST_VERSION_CONFLICT` before applying fields, recording a decision/audit or deleting evidence. A repeated terminal decision retains `CHANGE_REQUEST_NOT_PENDING`. Rejection/return inputs are unchanged by this increment.

The existing approval client passes the stable selected request ID and its displayed queue-row version directly to the API; it does not look up or replace the version with newer server state. Legacy unknown-version approval is disabled in that queue. Queue filtering/refresh, rejection, directory navigation and existing first-page behavior remain.

This is an incremental guard, not completion of transactional approval. Existing successful application/audit/cleanup behavior remains; fresh exact evidence validation, latest-lineage/stale-baseline/protected-context checks, applying only actual normalized differences, uniqueness/conflict handling, and full decision concurrency/rollback verification remain subsequent Task 6 work. Do not treat version match or an earlier available detail/preview as sufficient authorization to approve.

## Implemented fresh approval evidence guard (Task 6.2a)

Approval now rechecks the Superadmin under the reviewer-account lock before taking the existing Student/screening/request locks. The same reviewer-lock helper is reused by private COR retrieval. If request ownership/screening context changes between initial lookup and its current locking read, approval returns safe `409 CHANGE_REQUEST_STALE` before any file read or application. Pending/version/legacy guards remain.

For a matching pending version, approval independently calls the shared exact evidence inspector with current locking reads. It requires actual available bytes, original deadlines, matching owner/confirmed passed registration-purpose screening/file/digest/upload metadata and pending cleanup; it checks replacements, actual PDF size/signature/hash and expiry after the bounded byte read. Prior preview/detail availability is never used as authorization. Any non-available evidence returns `409 COR_EVIDENCE_UNAVAILABLE` with only safe availability/UTC deadline details before proposed fields are applied or decision/audit/cleanup occurs. Reviewer eligibility is checked again after inspection. Successful approval preserves the existing whole-request application, audit commit and subsequent evidence cleanup behavior in this increment.

This does not complete Task 6: latest-lineage validation, immutable registered/enrollment baseline comparison, active references and protected identity, changed-field-only application, safe uniqueness conflicts and full transactional/concurrency verification remain subsequent work. The context-movement guard is not a substitute for those stale-data checks. These changes add no route, migration, retention extension, UI behavior or return/resubmission action.

## Implemented approval lineage and baseline guards (Task 6.2b)

Approval now verifies current lineage metadata under locks before evidence/application. The selected pending version must form one complete linear same-owner chain to a valid root, with consecutive explicit versions, terminal returned/rejected predecessors, no approved predecessor, cycle, orphan, higher version or successor. A legacy root retains its unknown version; its first explicit successor is version 1. Other/missing roots and malformed or obsolete links produce safe `409 CHANGE_REQUEST_VERSION_CONFLICT`, with no foreign history or submitted values in details. Unrelated same-owner roots are outside the selected lineage.

Approval requires independently valid complete recorded extraction and registered snapshots plus the exact captured registered screening ID. Required original extracted Student Number, names, year and section cannot be filled from baseline/proposals; explicit unmapped extraction campus/program nulls remain valid. Unknown/incomplete/invalid historical context produces `409 COR_EVIDENCE_UNAVAILABLE` without reconstruction.

Current account names, locked Student profile and latest confirmed registration context are compared against the immutable registered baseline. Whitespace/blank-middle-name normalization preserves text spelling for the registered comparison. A changed name/year/section, protected Student Number/campus/program, academic period, validity or confirmed registration identity produces `409 CHANGE_REQUEST_STALE`. Missing current profile/context or inactive campus/program references also block approval. Current profile, confirmed registration, campus and program reads use locks; unrelated account timestamps are not a stale-data proxy. Current supported registration-purpose submissions require their captured registered screening to be that same confirmation screening. Correction-only workflow isolation still precedes any future creation of that flow.

Denial preserves newer registered values, proposals, decision/audit history, account state and temporary evidence; it does not extend deadlines or perform cleanup. This increment does not add migrations, endpoints, frontend behavior or historical values. Remaining Task 6 work includes applying only actual normalized differences (the existing successful path still assigns the five requested fields), final evidence deadline/commit checks, safe uniqueness/conflict handling and full atomic rollback/one-winner concurrency verification.

## Implemented changed-field application and final commit guards (Task 6.3a)

After existing reviewer/version/lineage/evidence/baseline checks, approval computes actual differences against the validated immutable baseline using existing whitespace/blank-middle-name normalization and backend Unicode casefold (strict integer comparison for year). Only differing supported fields are assigned. Equivalent unchanged names/section retain their registered spelling and receive no unnecessary profile/user updates. Stored proposals and snapshots remain immutable.

The captured effective evidence deadline is checked again after baseline validation and before application, then again after flushing the complete profile/decision/audit transaction immediately before commit. Equality means expired. Failure produces safe `COR_EVIDENCE_UNAVAILABLE` with availability/UTC deadline details. The application/audit/flush/commit block explicitly rolls back on failure, so late expiry or failed audit/write cannot leave a partial approval even for a direct service caller. Only a successful commit invokes the existing evidence cleanup afterward.

Approval audit metadata now contains only previous/new status and submission version with the existing actor/request identifiers; no proposed/registered values or file content/identity are added. No new route, DTO, migration, retention extension or frontend behavior is introduced. Relevant uniqueness/conflict handling and real multi-connection one-winner decision/rollback verification remain Task 6.3b; full transactional approval must not yet be described as complete.

## Implemented protected identity/conflict guards (Task 6.3b1)

Approval now independently rechecks ownership of the current protected email and registered Student Number using current locking reads through `AccountsRepository`. Each must still resolve to the stable Student account. Missing/different owners produce safe `409 CHANGE_REQUEST_STALE` before field application. Email and Student Number remain read-only; this adds no identity proposal/editor or historical email snapshot.

A database driver error in these identifier lookups rolls back and returns generic `500 INTERNAL_ERROR` without logging bound identifiers or driver messages. During the application/audit/flush/commit block, MySQL `1062` is translated only for exact known identity keys: `uq_student_profiles_number` returns `409 STUDENT_NUMBER_ALREADY_REGISTERED`; `uq_users_email` returns `409 CHANGE_REQUEST_STALE`. The whole transaction rolls back before either error. Other constraint/driver failures return generic `500 INTERNAL_ERROR` and are not mislabeled as identity conflicts. SQL, parameters, duplicate values, constraint names and driver text are excluded from responses and normal error logs.

Tests trigger actual MySQL identity unique violations by injecting duplicate rows into the approval flush and verify rollback/no leaked data; these do not establish real concurrent-decision behavior. No route/DTO, migration, retention or frontend change is added. Task 6.3b2 still needs real multi-connection one-winner/rollback verification, with final approval success-detail response alignment afterward before Task 6 completion.

## Implemented real decision concurrency verification (Task 6.3b2)

Independent committed MySQL connections now verify competing approvals and approve/reject decisions for the same and different Superadmins. Both callers intentionally cache pending state before the first decision commits; only one decision succeeds, the loser receives `CHANGE_REQUEST_NOT_PENDING`, and exactly one decision audit plus the matching profile outcome remains. Evidence is deleted only after the winning decision commits.

The tests reproduced a real MySQL `1213` deadlock when rejection held the Student/request locks while a same-reviewer approval held the reviewer-account lock: rejection's audit actor FK then needed that reviewer. The existing rejection path now uses the same reviewer-before-Student/screening/request lock order as approval/private retrieval and freshly rechecks reviewer eligibility. Rejection retains its existing reason/body/REJECTED semantics until Task 7; no manual return or versioned reject behavior is added here. No retry system, dependency or worker is introduced.

Additional races flush an approval's SQL and then fail its audit or pre-commit call. A third independent connection observes only the prior pending/profile state and no approval audit; after rollback, the waiting approval succeeds with one final audit/outcome. Separate connections also prove that a committed newer Student name or section is detected as stale despite the waiting reviewer's earlier cached values, with no decision, overwrite or evidence deletion.

These tests use synthetic committed rows exclusively in the owned disposable MySQL fixture, with scoped teardown. No application migration, browser/camera/device behavior or global deactivation/session-issuance race is claimed. Final approval success-detail response alignment remains Task 6.3b3 before Task 6 completion; manual return/resubmission remains Task 7.

## Implemented approval success-detail response (Task 6.3b3)

Successful `POST /profile-change-requests/{change_request_id}/approve` now returns `ReviewProfileChangeRequestDetail`, matching the Superadmin detail GET rather than the legacy flat request DTO. It invokes the existing approval transaction and post-commit cleanup first, then reuses the authorized safe detail serializer. The response contains approved request/version/reviewer metadata, actual post-decision current registered values, unchanged extraction/submission baseline and original proposal/diff, bounded history and `evidence.availability: RESOLVED`. Successful responses remain `no-store`.

No file identity/hash/path/token/clinical content or arbitrary snapshot keys are included. Failed deletion still leaves resolved evidence unavailable for preview while cleanup remains retryable. Student own reads retain their separate narrower DTO. The existing client ignores the mutation response body and refreshes the pending queue; API-boundary tests now supply the new nested detail shape while preserving clicked ID/version and CSRF behavior. Rejection still uses the existing flat response until Task 7's return compatibility work.

This completes Task 6's incremental approval work for the currently supported registration-purpose submission flow. It changes no transaction, decision/error, audit or cleanup behavior. Versioned fresh-COR resubmission and correction-only screening isolation remain Task 7; they must extend the existing purpose/context guards before creating that flow. Full Users/UI/end-to-end work and browser walkthrough remain later tasks.

## Implemented manual return endpoint (Task 7.1a)

`POST /profile-change-requests/{change_request_id}/return` accepts only required `submission_version` and `reason`. Version is a strict positive integer, or explicit null for an unknown legacy root; omission is invalid, and a version/null mismatch gives `CHANGE_REQUEST_VERSION_CONFLICT`. Reasons are trimmed before the 500-character limit and must be nonblank (`CHANGE_REQUEST_REASON_REQUIRED`), with no arbitrary word-count requirement. Unknown body properties are rejected through safe validation.

Only an active non-deactivated Superadmin can return the latest pending whole request, using reviewer-first then Student/screening/request locks and the existing lineage guard with narrowly scoped legacy-null support. Legacy versions/snapshots remain unknown; historical approved/rejected/returned decisions cannot be rewritten. Missing/expired/unavailable evidence or changed registered data does not prevent a reasoned return. A return changes no registered fields, account eligibility, enrollment validity, proposal or evidence deadline.

The request becomes `RETURNED` with its trimmed reason, reviewer and UTC review time, committed atomically with a safe `profile_change_returned` audit. Free-text reason is stored only in the request, never general audit metadata/logs. Failed audit/flush/commit rolls back before cleanup; database errors are sanitized. Existing private cleanup runs after successful commit and remains retryable on deletion failure. Deliberately missing metadata cannot supply a storage location: return never guesses a path, scans unrelated files or resurrects evidence. Normal metadata-backed resolved evidence is released immediately.

Success returns the existing safe Superadmin detail with `no-store`, immutable comparison/history and resolved evidence. The owning Student can read the outcome/reason through the existing narrow response. `can_resubmit` stays false until fresh-COR versioned resubmission ships. This increment leaves legacy `/reject` and its client unchanged; compatibility alias/client version propagation remains Task 7.1b. No migration, frontend behavior, new evidence upload flow or notification mechanism is introduced.

## Implemented reject compatibility and client return action (Task 7.1b)

`POST /profile-change-requests/{change_request_id}/reject` is now a deprecated compatibility alias for the same whole-request return service. It requires the identical strict `{submission_version, reason}` body as `/return`, including explicit null for legacy unknown version, and returns the same no-store safe review detail. New alias decisions are `RETURNED` with `profile_change_returned` audit metadata and post-commit cleanup. Historical `REJECTED` rows/reasons/events are not relabeled. Existing internal reject callers must also provide an explicit expected version; no hidden current-version fallback remains.

The existing pending queue now labels this action Return/Confirm return, asks what needs correction, trims the reason, caps the input at 500 characters and sends the clicked stable ID and displayed version to canonical `/return`. Legacy null is transmitted explicitly. Blank reasons are blocked locally; server validation remains authoritative. Success refreshes the existing `status=PENDING` queue and uses a generic return toast without copying the reason. Approval, cancellation, refresh/error paths, directory navigation and action element IDs remain. The existing first-page limitation is unchanged; no global lookup/completeness assumption is introduced.

Focused component/API tests cover both integer and null versions, correct record identity, CSRF, trimmed reason, refresh and reason-free toasts. Existing real independent-connection races now verify the reject alias also produces RETURNED while preserving one winner. No migration, new upload flow or notification mechanism is added. Manual return/compatibility work is complete; fresh-COR resubmission and correction-only purpose isolation remain Task 7.2.

## Implemented registration screening isolation (Task 7.2a1)

Enrollment-facing latest-screening reads, Student directory screening summaries and Counselor screening lists select only `REGISTRATION`. A newer `CORRECTION` row cannot displace registration status, select the target of registration confirm/reject/resubmit/recovery, or provide a fallback when no registration exists. Exact screening/file reads remain available to the authorized evidence workflow.

Registration confirm/reject/resubmit cores check ownership and purpose before mutation; shared activation independently requires matching registration evidence. Registration token issuance and digest lookup exclude correction evidence, and token resolution rechecks purpose on the locked row. A supplied correction token fails closed even alongside a valid session. Existing request-edit purpose checks remain authoritative.

This is partial isolation before fresh-COR resubmission: no endpoint creates `CORRECTION` rows. Cleanup and review-context purpose handling still require Task 7.2a2 before the new upload/version flow may be enabled. Existing enrollment validity and evidence deadlines are unchanged.

## Implemented cleanup deadline isolation (Task 7.2a2)

The existing cleanup worker selects files whose original upload time is seven days old, independently of mutable expiry metadata and screening submission time. Pending-request upload deadlines also select cleanup work. Both exact pending-evidence retention and open-file retention enforce the original file upload limit; extending an expiry field cannot postpone deletion. Equality at the deadline means expired.

Cleanup continues to lock and operate on the exact screening/request/file, for both purposes. Returning or expiring correction evidence preserves the separate registered screening, confirmation, validity, account eligibility and current profile. System return commits before byte deletion; deletion failures remain retryable without making the resolved request reviewable again. No new worker, endpoint, migration or CORRECTION upload flow is introduced.

Review/approval still accepts only the existing registration-purpose context. Separate correction-proof validation and registered-baseline comparison remain Task 7.2a3 before fresh-COR version creation may be enabled.

## Implemented separate correction proof reads (Task 7.2a3a)

Exact evidence availability/private preview can inspect a separate PASSED CORRECTION screening linked to the current registered enrollment. The proof cannot carry enrollment confirmation or validity. Its Student Number must match the current profile and confirmed registration. Mapped campus/program must agree; unmapped proof references use the current active registered references. Academic periods must agree when both are present. Current enrollment must be valid, ACTIVE and not operationally deactivated. The latest registration must still be the recorded baseline. Existing exact owner/file/digest/upload/deadline/byte checks remain shared with registration evidence, and informational reads do not acquire new locks or mutate business state.

This increment changes evidence reads only. Approval still rejects separate proof through its existing same-screening baseline guard until Task 7.2a3b adds and verifies separate-baseline approval. No endpoint creates correction-purpose uploads or new versions yet; available preview alone does not authorize approval.

## Implemented separate-baseline approval (Task 7.2a3b)

Transactional approval now distinguishes registration proof, whose screening must still be its enrolled baseline, from separate CORRECTION proof. Separate proof rechecks current valid enrollment, protected identity/references/period and eligibility through the shared proof scope check under the existing locks. The immutable registered snapshot and recorded enrollment screening remain authoritative: current editable/protected fields and period/validity must still equal that baseline before changed fields can be applied.

Approval uses the existing exact evidence checks, version/lineage/reviewer guards, final deadline checks, atomic decision/audit transaction, rollback and post-commit deletion. It never confirms correction proof, grants validity or changes current enrollment/account eligibility. The existing safe no-store approved detail response remains. Correction-purpose proof creation and linked fresh-COR versioned resubmission are still absent; these guards prepare the existing review flow without adding an upload endpoint.

## Implemented resubmission preflight (Task 7.2b1)

The internal `prepare_resubmission` service checks a Student actor before request access, freshly locks/rechecks the authenticated Student, scopes the predecessor lookup to that owner, and locks the predecessor screening/request and lineage. An explicitly supplied expected version must be a strict positive integer or null matching preserved legacy unknown version. Only the latest RETURNED/REJECTED predecessor is eligible; existing successors or another pending correction prevent revision. The pending guard uses a locking current read.

Preflight also locks the current confirmed REGISTRATION enrollment, latest registration attempt, profile and active campus/program. It requires an ACTIVE/non-deactivated Student, unexpired enrollment, no newer registration attempt and matching current protected identifiers/reference IDs. The future version uses actual current registered fields rather than the returned proposal or old snapshots. This operation returns internal locked context without committing, changing state, processing files or creating rows. Its caller must complete/recheck the eventual revision in the same transaction; a preflight result is not a reusable authorization token.

No resubmission endpoint or correction-upload/version creator exists yet. Proposal parsing/normalization, fresh passing proof, immutable linked version creation, transactional audit/storage failure handling and concurrent resubmission verification remain before enabling capability; `can_resubmit` stays false.

## Implemented revision proposal input (Task 7.2b2)

Internal `parse_resubmission_proposal` accepts multipart JSON text as one object containing only first/middle/last name, year level and section. Malformed/non-object JSON, duplicate keys and non-JSON numeric constants are rejected with safe `422 INVALID_PROFILE_EDIT`; protected/unknown properties return `422 FIELD_NOT_EDITABLE` without echoing values. The decoded-object normalizer is reusable inside the eventual transaction.

Omitted fields retain the actual current registered baseline. Explicit null is accepted only for middle name; blank middle name normalizes to null. Existing Unicode whitespace normalization, field length limits and strict integer years 1-10 apply without coercion. At least one normalized, Unicode-casefold-aware difference is required, otherwise `422 NO_CORRECTION_CHANGES`. The returned complete canonical proposal contains only the five editable fields and does not mutate the baseline.

These helpers do not authorize resubmission or write data. No endpoint, proof/version creation, storage flow or capability change is added; `can_resubmit` remains false until the complete transaction is implemented and verified.

## Implemented scratch correction screening (Task 7.2b3)

Internal `screen_correction_document` freshly locks and checks the Student, validates the PDF, and reuses existing dependency checks, private storage, screening engine and structured extraction mapping. Only passing automated screening with usable required names/year/section may produce transient PASSED CORRECTION proof. The proof must match the recorded current/latest valid registration, Student Number, mapped active campus/program and compatible known academic period through the shared enrollment scope guard. Unmapped proof references retain the registered active-reference fallback.

It returns an unsaved proof plus the SHA-256 digest of the input bytes. It does not add rows, confirm enrollment, issue a registration token, grant validity, mutate history/profile or commit. Scratch bytes are released on success and all processing failures; deletion failure preserves the existing pending marker for bounded abandoned-upload cleanup and logs only a generic retry code. Missing dependencies return a safe availability error.

This processing result is not durable evidence or reusable authorization. The eventual revision transaction must recheck locked preflight/context, bind exactly the screened bytes/digest, preserve the original `submitted_at` deadline origin when storing evidence, and atomically create proof/file/new version/snapshots/audit. No endpoint or capability change is introduced in this increment.

## Implemented internal atomic resubmission (Task 7.2b4)

Internal `ProfileChangeService.resubmit` now integrates locked preflight, strict proposal parsing and scratch COR screening. It rechecks predecessor/version/lineage/current enrollment after screening, re-parses against actual current values, verifies the screened input digest and protected proof context, then creates separate PASSED CORRECTION proof, exact private file metadata and the next linked PENDING request with fresh immutable extraction/current baseline snapshots. Legacy unknown predecessors start explicit version 1; versioned predecessors increment within the same root. Old proposals, snapshots, decisions and current profile/enrollment remain unchanged.

File upload time and original deadline use the scratch proof's original submitted_at, not its later durable write time. Final expiry is checked after flushing the whole proof/file/version/audit transaction and before commit. The safe `profile_change_resubmitted` audit contains status/version only. All failures roll back SQL and release newly stored bytes; failed deletion keeps the existing marker for bounded cleanup. Pending-guard duplicates map to a safe conflict and other driver errors are sanitized. Successful commit clears the marker without releasing pending evidence.

This remains an internal service with no resubmission route or capability flag. Focused transaction and sequential replay verification does not replace dedicated independent-connection resubmission races; those and remaining failure-boundary checks precede endpoint enablement.

## Verified resubmission races and commit cleanup (Task 7.2b5a)

Real independent MySQL connections now verify same-predecessor resubmission for both registration-purpose and correction-purpose predecessor evidence. Versioned and legacy-null predecessors have exactly one committed linked pending successor and one resubmission audit; the waiting contender, even with an earlier repeatable-read snapshot, receives the version conflict. A first transaction that fails after flushing releases its locks and rows so the waiting contender can create the single successor. A third connection cannot observe the uncommitted version. Registered profile/account and predecessor history remain unchanged, and the winning exact evidence is available.

Injected failure before the actual database commit also verifies rollback of the complete flushed transaction and release of newly stored bytes. If byte deletion fails, the existing marker survives and existing bounded abandoned-upload cleanup removes that orphan on retry, without making a correction row or exposing private paths in logs. These tests require no production changes, migration, new cleanup worker or dependency.

This verifies one-winner revision and selected commit/deletion boundaries, not ambiguous post-commit acknowledgement failures or all enrollment/deactivation interleavings. Current-enrollment/eligibility races remain Task 7.2b5b before the multipart endpoint/capability is enabled.

## Verified enrollment and eligibility races (Task 7.2b5b)

Independent MySQL connections now verify both Student-lock orders for operational deactivation, expired registration validity and a newer registration attempt, against both registration-purpose and correction-purpose predecessor evidence. Waiting resubmissions hold stale Student/profile/enrollment ORM objects and an earlier repeatable-read snapshot. When the eligibility change commits first, fresh locking checks deny revision before scratch screening or new version/audit creation. When revision commits first, exactly one version records its then-current registered baseline; the later eligibility change persists without overwriting the profile or predecessor history.

A later deactivation or expired validity makes the pending evidence unavailable for review; a newer registration attempt marks it replaced. The tests use scoped synthetic changes under the existing Student-first locks. They do not implement Users Management, session revocation or an automatic system-return workflow for those synthetic writes. No production change was needed. These checks prepare the internal service for multipart endpoint work; the endpoint and capability flag remain absent.

## Implemented multipart resubmission API (Task 7.2c1)

`POST /profile-change-requests/{change_request_id}/resubmit` now accepts a Student session with the existing CSRF protection. COR tokens alone do not authorize it. The body requires exactly one `file`, `submission_version` and `proposed_changes` multipart part; duplicates and extra parts are rejected. Version is positive decimal text (maximum 20 characters) or literal `null` for a preserved legacy unknown version. Proposal text is bounded to 4096 characters and uses the strict editable-object JSON parser. Required/type/pattern validation uses the standard safe validation envelope without echoing inputs.

The route reads at most the configured PDF limit plus one byte and rejects oversized uploads before calling the verified atomic service. Current ownership, eligibility, exact predecessor version/lineage, passing protected-context proof and no-change checks remain authoritative in that service. File processing and SQL work run through the existing thread pool, while multipart/file reads use the async upload interface. No new dependency, transport or storage mechanism is introduced.

Success is `201` with the existing narrow Student-owned status/comparison DTO for the new version, matching its owner GET. It includes current registered values, submitted editable proposal and safe lineage/status metadata, without reviewer identity, private file/hash/path, token or raw extraction snapshot JSON. Success and handled domain errors are `no-store`. Other/missing requests have identical safe not-found outcomes. UI capability indicators remain unchanged pending their separate response/eligibility integration; no new frontend flow is added here.

## Implemented owner resubmission availability (Task 7.2c2)

Student list/detail items, including the 201 resubmission response, now include boolean `can_resubmit`. It is an informational owner action flag: true only for the latest structurally valid RETURNED/REJECTED lineage version (including preserved legacy null), with no other pending correction, an ACTIVE/non-deactivated Student, enabled screening, usable current profile and current valid/latest confirmed REGISTRATION enrollment with matching protected number and active references. Old COR availability and unknown historical snapshots do not block a fresh-evidence revision. Correction-purpose screenings never replace the enrolled baseline.

Capability derivation uses nonlocking metadata/reference/enrollment reads and does not mutate, commit, audit or inspect COR bytes. Missing/inconsistent current or lineage context fails closed. Lists retain owner-scoped SQL pagination and existing projections. Superadmin detail keeps `can_resubmit: false`, because this is an owner action rather than a reviewer permission.

A read flag is not authorization and may become stale immediately. The multipart POST independently performs the existing locked eligibility/version/lineage/proof checks; mutation lineage queries retain their locking defaults. No frontend resubmission flow is added by this response increment.

## Three independent states

| Concern | Contract |
|---|---|
| Enrollment/account eligibility | Keep `account_status`: `PENDING_VERIFICATION`, `ACTIVE`, `VERIFICATION_EXPIRED`, with existing screening and validity checks. |
| Operational deactivation | `users.is_deactivated` defaults to false. Implemented Users operations and authentication/HTTP/COR-token/socket guards enforce it independently of enrollment and correction state. |
| Correction review | New versions use `PENDING`, `APPROVED`, `RETURNED`. Preserve historical `REJECTED` rows as terminal history, without relabeling them as returned. |

An eligible Student who submits corrections completes registration, becomes `ACTIVE`, and can sign in and use existing authorized features while the proposal is pending. Submission and decisions never clear deactivation, repair failed screening, extend enrollment validity, or independently activate an account. The registration response still does not create a session.

Reactivation clears only `is_deactivated`; it neither changes `account_status` nor restores revoked sessions. Pending/expired Students can sign in only for the existing restricted account/reverification access. An expired formerly active Student still needs the existing current-COR renewal. No status is restored from a remembered pre-deactivation value.

## Fields and normalization

Normalize before validation, comparison, storage, and deciding whether a request exists. Backend results are authoritative; frontend comparison is a preview.

| Field | Stored canonical value | Comparison and validation |
|---|---|---|
| `first_name`, `last_name` | Trim ends and collapse Unicode whitespace to one ASCII space; preserve case | Required, 1–100 characters after normalization; compare Unicode casefolded strings. |
| `middle_name` | Same normalization; empty becomes `null` | Optional, at most 100 characters; null/blank compare equal. A nonempty proposal against null extraction is a real change. |
| `year_level` | Integer | 1–10, matching the existing backend; reject booleans/fractional values; compare integers. UI must support the same range. |
| `section` | Trim/collapse whitespace; preserve case | Required, 1–50 characters; compare casefolded strings. |

Do not add accent removal, punctuation stripping, or name parsing rules. Share normalization vectors across frontend/backend tests, including whitespace, null middle names, case-only changes, and Unicode casefold differences. The UI must handle a server result with no request even when its preview detected a difference.

Initial submission keeps the existing confirmation DTO: `student_number`, the five editable fields, `campus_id`, `program_id`, and nullable `academic_period`. Student Number is trimmed/uppercased and must match the screened strict UCC identifier; mapped reference IDs and academic period must still match. Unmapped campus/program selections must refer to active reference rows and are registration selections, not correction proposals. Reject unknown fields and attempts to submit owner, status, reviewer, email, or authorization values.

## Registered baseline and immutable evidence

For initial registration, establish the registered baseline from the passed extraction plus permitted unmapped campus/program selections. Keep a missing extracted middle name null; do not apply a proposed addition before approval. Missing required extracted fields fail screening, rather than being filled from a proposal. Existing successful no-change registration remains a plain confirmation with no request.

For enrollment renewal, preserve the existing successful renewal behavior; snapshot the registered baseline established by that confirmation before queuing any correction. The queue must not write proposed values into `users`, `student_profiles`, or extraction fields. Current registered information continues to drive display, login, ownership, eligibility, and authorization until approval.

Each new request row is one immutable submitted version. Extend the existing table only with the missing metadata needed for:

- Stable `student_user_id`, exact `cor_screening_id`, submission version, and previous/root request linkage.
- Immutable original structured extraction (including explicit nulls), registered baseline, and proposed values. Keep existing requested columns where useful; no duplicate proposed-value store is necessary.
- Exact private file identity and expected SHA-256 digest, upload time, and original expiry, retained as safe internal evidence metadata after file deletion. Do not rely on a file FK that disappears during cleanup to identify historical evidence.
- Existing submission time (`created_at`), review status, reviewer, review time, and return reason.

Snapshots contain only necessary structured registration fields and screening/context metadata, never PDF bytes, raw OCR text, or decoded barcode payloads. Submission version starts at 1 and increments within a request lineage. Preserve old submitted rows and decisions; only the pending row's decision metadata changes once. A resubmission inserts a new row, never updates the old proposed fields. An evidence re-upload creates a new screening row for the new version, never overwrites the old evidence context.

Correction-only screening needs an explicit purpose (`REGISTRATION` or `CORRECTION`) on `cor_screenings`. Existing rows default to `REGISTRATION`. Existing registration/latest-enrollment/validity queries must exclude correction-only screenings. Correction-only screening reuses the screening engine and private storage, but cannot activate, renew, expire, or rewrite the account/profile. This distinction is necessary because a fresh review document must not become a new enrollment grant.

No previous registered snapshot can be reliably reconstructed for existing rows: `_activate()` has mutated extraction fields, registered values may since have changed, and COR bytes have been deleted. Migration must leave added historical snapshots/evidence/version lineage unknown where unavailable, preserve existing statuses and decisions, and create no synthetic requests. Show unknown historical comparisons as unavailable. Legacy pending requests may be returned with a reason, but cannot be approved without the new verifiable context; Student resubmission supplies fresh screened evidence and creates the first explicit version in a linked lineage. Existing approved rows remain approved, without implying that the new evidence checks were performed.

## Transitions, duplicates, and concurrency

| Action | Preconditions | Result |
|---|---|---|
| Initial `request-edit` | Own confirmable, unexpired, passing registration screening; existing eligibility checks; actual normalized differences | Activate through existing confirmation with the baseline, create version 1 `PENDING`, clear COR token. Commit activation/request/audit together. |
| No-change `request-edit` | Same registration checks; no actual differences | Existing successful confirmation; `change_request: null`; delete COR as before. |
| Approve | Active non-deactivated Superadmin; latest `PENDING` version; intact, available, unexpired exact evidence; unchanged baseline/context | Apply only changed allowed fields; mark entire version `APPROVED`; atomic profile/decision/audit commit; then queue evidence deletion. |
| Return | Active non-deactivated Superadmin; latest `PENDING` version; useful reason | Mark entire version `RETURNED`; preserve baseline/proposal; atomic decision/audit commit; then queue evidence deletion. No profile changes. |
| Resubmit | Owning non-deactivated `ACTIVE` Student, valid existing enrollment; latest `RETURNED` (or legacy terminal `REJECTED`); fresh passing COR; actual differences | Insert next version `PENDING`, linked to the reviewed version, with fresh immutable snapshots/evidence. No account/profile changes. |
| Evidence expiry/replacement/new enrollment | Associated pending evidence expires/is superseded | Return pending version with safe system reason `COR_EVIDENCE_EXPIRED` or `SUPERSEDED_BY_NEW_COR`; reviewer null, timestamp and audit recorded. Keep account eligibility independent. |

Return reasons are trimmed, 1–500 characters, and must explain what to fix; reject whitespace-only input. Store reason only in the purpose-bound request, never generic logs/notifications. Backend validates useful nonblank text and length; UI prompts for an actionable reason without an arbitrary minimum word count.

Maintain at most one pending correction per Student (the existing stronger restriction also ensures one per screening context). Enforce it under the Student lock and a MySQL-compatible uniqueness guard. New versions require the expected previous `submission_version` and latest predecessor ID. An older returned/rejected version cannot be resubmitted twice or approved. Approved versions are terminal; a new unrelated profile-edit workflow is outside scope.

Review action bodies require `submission_version` (integer >= 1 for new versions). For a legacy row whose version was never preserved, require explicit null instead of inventing a version; allow this only for return/resubmission, never approval. In multipart resubmission, encode that legacy null as the literal `null`. The path ID and locked predecessor state still prevent duplicate legacy resubmission. The first new version after legacy history is version 1. Lock the target Student, then screening, then request; cleanup, replacement, return, approval, and resubmission must use the same ordering when touching those records. Re-read authorization, latest lineage state, evidence identity/digest/expiry, passing screening, registered baseline, protected identifiers, active references, and existing eligibility rules inside the transaction. Do not use only `users.updated_at` to detect stale data: compare the stored relevant baseline and enrollment context. Unrelated profile timestamps do not invalidate review.

Apply only normalized differences, leaving unchanged fields untouched. Recheck existing email/Student Number uniqueness and ownership rules when applicable, even though they are not editable. Convert relevant database uniqueness races into safe conflicts. A change to registered comparison fields, protected Student Number, reference context, or enrollment screening since submission produces `409 CHANGE_REQUEST_STALE`; never overwrite newer values. Failed approval leaves the pending proposal/profile unchanged; the reviewer can reload or return it.

Initial duplicate submissions after the first commit return the existing conflict (`SCREENING_NOT_CONFIRMABLE` or `CHANGE_REQUEST_PENDING`), without creating another row or reactivating anything. Review/resubmit version mismatch returns `CHANGE_REQUEST_VERSION_CONFLICT`; repeated decisions return `CHANGE_REQUEST_NOT_PENDING`. Concurrent decisions have one winner; no silent successful replay. Failed fresh-COR screening creates no new pending version, leaves the returned version/profile intact, and discards the rejected upload using existing cleanup controls.

## COR retention and review availability

The approved narrow exception is: **only a COR with a pending correction may survive Student registration confirmation, and only until approval, return, replacement, or the original upload deadline (`uploaded_at + 7 days`), whichever occurs first.** No-change confirmation still deletes immediately. Submission, opening a preview, retrying, or resubmitting proposal fields never extends an existing file's deadline.

Returning deletes the reviewed COR. Revision therefore requires a fresh current COR upload and passing screening; its own seven-day window begins at that new upload. Before creating a correction version, require its screened Student Number to equal the current registered Student Number and mapped campus/program to agree with that context. Unmapped references use the current registered active reference IDs, never proposed replacements. Compare academic periods when both the enrollment context and fresh extraction contain them; preserve absence as unknown because the existing field is optional. Missing required identity/context or invalid documents cannot be overridden by Superadmin review. A mismatch needing Student Number/reference correction is outside the supported fields and requires a separate business decision, not an automatic identifier update.

Expiry must return the correction without expiring the otherwise valid registered enrollment. The existing cleanup loop must exempt a passed registration screening's file only while its exact correction is pending and before the original expiry; it must still delete after expiry/decision/replacement and retry failures. Make a decision and queue cleanup transactionally, then delete bytes after commit. A failed deletion never makes evidence available for review again. Approval and preview must independently enforce expiry even between cleanup passes.

Private content is served only through the request-scoped authenticated Superadmin route, as `application/pdf` with a fixed safe filename and `Cache-Control: no-store`. Resolve the request's exact file metadata, owner, screening, purpose, hash, pending status, and deadline; never substitute the Student's latest file. No storage keys, paths, original filenames, public URLs, token URLs, raw barcode payloads, or bytes appear in JSON. Return `COR_EVIDENCE_UNAVAILABLE` when evidence is missing, deleted, replaced, corrupt, or expired. Include only a safe availability code and deadline in details. Block approval; allow a reasoned return. Review history remains readable after deletion but has no historical COR preview.

Approval affirms that the proposed corrections match this submitted COR; it does not certify University issuance. No permanent COR retention period is introduced. Reviewing after seven days requires return/fresh evidence; review beyond that window is intentionally unsupported. Existing deleted evidence is irrecoverable. Upload/privacy wording must disclose the bounded exception and fresh-evidence requirement.

## Correction API contract

All paths are under `/api/v1`. List endpoints use `{items, page, page_size, total}`, page >= 1, default size 20, maximum 100, SQL pagination, and deterministic ordering. Unknown statuses/roles/fields return `422 VALIDATION_ERROR`; omit `status` to list every status including historical `REJECTED`. Frontend review queue explicitly sends `status=PENDING`. All correction/user responses are `no-store`.

| Method/path | Caller and shape |
|---|---|
| `POST /cor-screenings/request-edit` | Existing Student session or own `X-COR-Token`; same initial DTO and `{screening,user,profile,change_request}` response, now with immutable request metadata. No-change returns null request. |
| `GET /profile-change-requests` | Superadmin sees queue; Student sees only own requests through the same backend-scoped route. Optional `status`; sort newest submission then ID descending. Items carry request metadata, safe Student summary, and changed-field names; no document/proposed values in generic notifications. |
| `GET /profile-change-requests/{change_request_id}` | Owning Student or Superadmin; detail shape below. Other Students receive concealed `404 CHANGE_REQUEST_NOT_FOUND`. |
| `GET /profile-change-requests/{change_request_id}/cor` | Superadmin only, pending exact evidence; PDF response as above. Student/Counselor/Guidance Staff receive 403. |
| `POST /profile-change-requests/{change_request_id}/approve` | Superadmin; JSON `{submission_version: integer >= 1}`; 200 updated detail. No proposed-field overrides or partial approval. |
| `POST /profile-change-requests/{change_request_id}/return` | Superadmin; JSON `{submission_version, reason}`; 200 updated detail. |
| `POST /profile-change-requests/{change_request_id}/resubmit` | Owning Student session, CSRF; multipart `submission_version`, `file`, `proposed_changes` (JSON object limited to the five editable fields); 201 new-version detail. At least one difference from current registered baseline is required (`422 NO_CORRECTION_CHANGES` otherwise); omitted fields retain baseline values and only middle name accepts null. |
| `POST /profile-change-requests/{change_request_id}/reject` | Compatibility alias for return during client migration; enforce the same version/reason/access rules and produce `RETURNED` for new decisions. Preserve historical `REJECTED` rows. |

Superadmin detail response (Student status reads and resubmission success use the narrower owner DTO described above):

```text
{
  change_request: existing safe request fields + submission_version,
                  previous_change_request_id, root_change_request_id,
  student: {user_id, email, first_name, middle_name, last_name, account_status},
  extracted_values: structured registration snapshot | null for legacy,
  registered_values_at_submission: registration snapshot | null for legacy,
  current_registered_values: current registration fields,
  proposed_changes: changed allowed fields only,
  changed_fields: [allowed field names],
  evidence: {availability, expires_at},
  history: [{change_request_id, submission_version, status, created_at,
             reviewed_at, decision_reason}],
  can_resubmit: boolean
}
```

The snapshots include names, year/section, Student Number, campus/program IDs, and academic period for review context; protect baseline account/enrollment identifiers internally without exposing token/hash/storage metadata. `proposed_changes` is computed from immutable baseline/request values. For legacy requests, report proposed editable values and unknown historical comparison explicitly instead of guessing a diff. Evidence availability is derived, not another persisted workflow: `AVAILABLE`, `UNAVAILABLE`, `EXPIRED`, `REPLACED`, `CORRUPT`, `RESOLVED`, or `LEGACY_UNKNOWN`; only `AVAILABLE` permits preview/approval. Authorized Students may read all their version proposals, outcomes, and reasons; omit reviewer user IDs and operational metadata from their response. Superadmin sees reviewer IDs for history. History is limited to this owner's lineage, never a general audit feed. Large history is paginated through `GET /profile-change-requests?root_change_request_id=...`; detail includes only the selected version and immediate predecessor history entries, with the list providing complete history. Verify root ownership before filtering, concealing another Student's root with 404.

Use existing safe error envelope. Keep existing registration errors, plus:

| HTTP/code | Meaning |
|---|---|
| 401 existing session/token errors | Authentication failed; retain existing CSRF semantics. |
| 403 `FORBIDDEN_ROLE` / `ACCOUNT_DEACTIVATED` | Role lacks permission / operationally disabled. |
| 404 `CHANGE_REQUEST_NOT_FOUND` / `USER_NOT_FOUND` | Missing or deliberately concealed resource. |
| 409 `CHANGE_REQUEST_PENDING` / `CHANGE_REQUEST_NOT_PENDING` | Existing pending request / decided request. |
| 409 `CHANGE_REQUEST_VERSION_CONFLICT` / `CHANGE_REQUEST_STALE` | Wrong predecessor/version / changed registered or enrollment context. |
| 409 `COR_EVIDENCE_UNAVAILABLE` | Exact review evidence cannot be used; no automatic approval. |
| 409 `STUDENT_NUMBER_ALREADY_REGISTERED` | Existing uniqueness rule failed; do not identify the other account. |
| 422 `FIELD_NOT_EDITABLE` / `INVALID_PROFILE_EDIT` / `NO_CORRECTION_CHANGES` | Unsupported change / invalid editable value / empty revision. |
| 422 `CHANGE_REQUEST_REASON_REQUIRED` | Return reason is blank. |
| 409 `COR_CONTEXT_MISMATCH` | Fresh review evidence belongs to another identity/enrollment context. |

Errors must not echo submitted values, another account's identifiers, SQL, paths, OCR/barcode content, or tokens. Details may include safe field names, current status/version, or availability codes only after authorization.

## Frontend workflow contract

Superadmin navigation exposes Users, Registration Corrections and Account Recovery (the existing separate Student directory route). These pages share consistent headers, filters, table and pagination presentation, status badges and responsive detail dialogs. Dialogs constrain scrolling, move and contain keyboard focus, close on Escape and restore focus to the triggering control. Users supports server-paged search and filters, safe typed detail, and explicit selected-account deactivate/reactivate confirmations; protected roles and self have no status action. Correction review provides status filtering, structured extraction/baseline/current/proposal comparison, selected-version decisions and complete paginated lineage history. Unknown historical snapshots are displayed as unavailable; a known absent middle name is displayed as none. Conflicts refresh authoritative state without silently retrying a decision against a newer version.

Private COR previews use authenticated no-store blob responses and temporary object URLs revoked on close, navigation, expiry or decision. No evidence URL is persisted. Students retain registration access while active and see their own outcomes, reasons and comparisons. Only server-advertised eligible revisions expose the five-field editor and fresh PDF upload; multipart submission preserves the selected request ID and displayed version, encoding legacy null literally. Forms retain input after errors. Lists expose loading/error/retry/empty states and all server pages, ignore obsolete responses, and never infer completeness from the first page.

## Users Management contract (backend and frontend implemented)

Only an active, non-deactivated Superadmin may use the new users operations. Preserve existing Counselor read-only Student directory behavior. List/search all four existing roles; only Student/Counselor accounts may be deactivated/reactivated. Superadmin and Guidance Staff targets are protected (`403 USER_STATUS_CHANGE_FORBIDDEN`), including self. This release adds no Superadmin status-changing path, so it cannot disable the last active Superadmin. Any future such path must protect that invariant transactionally.

| Method/path | Request and response |
|---|---|
| `GET /accounts/users` | Optional `q` (trimmed, max 320), `role_code`, existing `account_status`, `is_deactivated`, `page`, `page_size`; list safe summaries. Search name components, email, and currently registered Student Number using escaped substring matching; never search proposals. Stable last name, first name, user ID order. |
| `GET /accounts/users/{user_id}` | Safe account details and nullable Student profile; no clinical joins. |
| `POST /accounts/users/{user_id}/deactivate` | Empty JSON object; 200 updated safe detail. Lock target, set flag, revoke all live sessions with `ACCOUNT_DISABLED`, and audit in one transaction. Repeated action returns current state without duplicate transition audit. |
| `POST /accounts/users/{user_id}/reactivate` | Empty JSON object; 200 updated safe detail. Lock target, clear only flag and audit; leave enrollment restrictions unchanged. Repeat is likewise idempotent. |

Summary allowlist: `user_id`, email, role, account status, `is_deactivated`, names, nullable registered Student Number, created/updated timestamps. Detail adds only nullable profile `{student_number,campus_id,program_id,year_level,section}`, safe campus/program labels, and enrollment `valid_until` when relevant. No password/token/session records, COR paths, proposed corrections, messages, notes, assessments, clinical documents, appointment concerns, or SOS answers. Correction detail remains a separate purpose-bound response.

The auth session-user response may add `is_deactivated`; no correction status is needed in generic auth responses. Login, COR-token resolution, recovery, and protected request/socket checks must enforce deactivation. Serialize session issuance and deactivation with the same target-user lock so no live session escapes revocation through a concurrent login. Reactivation requires a new login. Existing sockets must use the existing session revalidation/closure mechanism; session revocation must not leave a previously authorized socket usable indefinitely. Recheck before sensitive socket actions; no new transport is introduced.

Do not cancel appointments, remove slots, modify conversation/clinical records, or transfer Counselor assignments. Existing participant-active checks can make a deactivated participant unavailable for actions; scheduling and coverage decisions remain separate business work. Users detail must not reveal those clinical dependencies. Keep new actions separate from registration cancellation and Superadmin recovery; recovery must not clear `is_deactivated` or bypass review.

## Implemented Users security and concurrency boundaries

### Counselor account creation and editing (user-approved 2026-10-26)

An active, non-deactivated Superadmin may create a Counselor and edit an existing Counselor's names/email. This narrowly supersedes prior developer-only staff provisioning and no-provisioning release scope. Counselor remains the highest authority for counseling operations; this grants no clinical access, arbitrary role changes, invitations, password reset/delivery, hard deletion or Student/other-staff profile editing.

| Method/path | Strict input and result |
|---|---|
| `POST /accounts/users` | `email`, `first_name`, optional nullable `middle_name`, `last_name`, and initial `password` (8–128 characters, entered by Superadmin). Server fixes role to COUNSELOR, account status to ACTIVE and deactivation to false; 201 safe `ManagedUserDetail`. No Student profile/COR/enrollment or clinical rows are created. |
| `PATCH /accounts/users/{user_id}` | All four editable fields (`email`, `first_name`, explicit nullable `middle_name`, `last_name`) plus timezone-aware `expected_updated_at` copied from the displayed detail; 200 safe detail. Missing/non-Counselor targets return 404/403; changed timestamps return 409 `USER_EDIT_CONFLICT`. Password, role, account status and deactivation are not editable through this route. |

Names normalize whitespace before existing 100-character limits; blank middle names become null. Email is validated/trimmed and must not duplicate any account or shadow an existing Student Number login identifier. Existing SQL email uniqueness handles competing writes; conflict errors never expose SQL, hashes, another account or input values. Unknown fields are rejected. Success and handled errors are no-store, with existing session/CSRF enforcement and fresh locked Superadmin checks.

Creation hashes the initial password through existing Argon2id helpers; password plaintext exists only in the submitted form/request and is never returned, audited, persisted, emailed or displayed after success. Superadmin must share it privately outside this workflow. No credential reset/delivery or forced-password-change mechanism is introduced.

Editing locks the Superadmin then the target User and compares the exact displayed updated timestamp. Successful changes advance it monotonically. Name-only edits preserve sessions; email changes revoke all sessions with `ACCOUNT_UPDATED` in the same transaction. Login rechecks the email resolved before locking so a concurrent old-address login cannot issue a session after the rename. Password hash, stable User ID, role/status/deactivation, scheduling, assignment and clinical data remain unchanged. No-op edits do not advance the timestamp or duplicate audits. Stale forms retain input and require the user to cancel/reload details; they never silently retry against a new timestamp.

Creation/edit and audit commit together; failure rolls back users and session revocations. Events `counselor_account_created`/`counselor_account_updated` carry actor/target IDs, safe fixed role/status or changed field names and a session-revocation boolean only. No names, email values, passwords or clinical data enter audit metadata. The Users UI provides Create Counselor and Counselor-only Edit actions using the selected record ID and detail timestamp; existing paging, filters, recovery and separate status controls remain available. No schema migration is required.

### Existing Users status/session enforcement

Users operations reuse accounts, auth, audit and existing socket revalidation. List/count/filter/paging run in SQL over accounts and current Student profiles only; substring search escapes wildcard characters and trims before enforcing the 320-character limit. Details project typed safe profile/reference labels and confirmed registration validity, never correction evidence or clinical content. Private routes set no-store on success and handled errors; validation errors omit untrusted client key names and values. Dates/timestamps use the existing UTC convention.

Status changes freshly lock/recheck the Superadmin before the target User. Only Student/Counselor targets are permitted. Flag transition, all-session revocation (ACCOUNT_DISABLED) and safe previous/new flag audit commit atomically; rollback restores both flag and sessions. Repeated actions do not duplicate transition audits. Reactivation preserves account/enrollment state and never revives a session, including residual sessions from pre-existing disabled state.

Login verifies credentials, locks and refreshes the same target User, rechecks current credentials/status, and issues/replaces sessions under that lock. HTTP authentication uses User-before-session ordering and commits authentication/activity before domain participant locks. Domain mutations retain their own authorization checks. Fresh short-lived socket revalidation is read-only and does not renew idle activity. Deactivation is checked independently of session revocation; COR-token resolution and recovery cannot bypass it.

Calls reauthorize before each signaling message as well as on their existing periodic timer. Messaging/appointment notification sockets revalidate by elapsed time even with continuous inbound traffic. Existing call queues deliver and close on the peer's owning event loop; disconnect notification occurs before cancellable cleanup. No new transport, raw-media storage or persistent signaling history is introduced. Disabled Counselors are excluded from booking availability; existing appointments, assignments and clinical records are not cancelled or rewritten.

## UI, audits, and acceptance gates

Superadmin navigation has Users, Registration Corrections, and existing account/sign-out controls. Reuse the existing table/detail and field comparison presentation; provide filters, complete pagination, loading/empty/errors, confirmation for deactivation/reactivation, and stale-decision reload feedback. Separate changed fields from unchanged context. Approval wording states document consistency, never authenticity. The server remains authoritative.

Student `#registration` shows current registered information separately from pending proposal values/status. Use “Your account is active. Your requested information changes are awaiting review.” only when the account is actually active and not deactivated. Show approved results and return reasons with allowed revision actions; do not present extraction snapshots as the current profile after approval. No blocking overlay or warnings on unrelated pages. No sensitive details in generic toasts/notifications.

Use existing `audit_events`: actor, action, request/user ID, previous/new status, submission version, timestamps and safe outcome codes only. New events include `profile_change_returned`, `profile_change_resubmitted`, `account_deactivated`, and `account_reactivated`; preserve historic events. Submission/profile/decision and audit must commit together. System expiry/supersession has null actor/reviewer plus safe reason code. Never audit field values, PDF content, free-text return reasons, passwords, raw tokens, or decoded barcode payloads. Document access may record only actor/request ID and safe outcome.

Each implementation task includes focused tests: normalization/null extraction; no-change behavior and pending login; owner/role/CSRF boundaries; immutable versions and duplicate submission; legacy unknown snapshots; exact private evidence and hash/expiry/replacement failures; return/new-upload resubmission; one-winner decisions and stale/unique conflicts; deactivation/session issuance races, revoked sockets, restricted reactivation, protected roles; and user-response clinical exclusions. Verify real Alembic upgrades/data preservation in the disposable MySQL fixture, update its migration loader, and regenerate OpenAPI only after routes change. Frontend tests should exercise API responses, page completeness, and stable account IDs. Final checks include relevant suites/build and an honest browser/manual-check report.
