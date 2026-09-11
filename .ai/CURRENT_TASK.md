# CounselConnect - Current Task

**Status:** COMPLETED (2026-09-11)
**Risk class:** MEDIUM (calendar availability calculation; no schema or authorization change)

**Task:** Replace default calendar hours with actual remaining availability and keep today's count current.

## Outcome

- Calendar reads all future AVAILABLE slots in the requested range, excludes time blocks and owner-specific whole-day blocks, and returns distinct Manila start times. Counselor scope and active-account authorization are preserved.
- Calendar counts and selected-day buttons remove elapsed times every second and on focus without renewing session activity. Empty days show "No times left".
- Updated the appointment contract and added frontend, service-unit, and MySQL integration regressions.

## Verification

- Frontend: 32 tests passed; production build passed.
- Backend calendar unit tests: 4 passed.
- MySQL appointment integration suite: 54 skipped because COUNSELCONNECT_TEST_DATABASE_URL is absent; SQL persistence verification remains outstanding.
- git diff --check passed.

## Limitations

- Other users' booking changes arrive on the existing 60-second background refresh; elapsed-time removal is local every second.
- Local backend restarted with the changes; health returned 200 and unauthenticated calendar access returned 401.
