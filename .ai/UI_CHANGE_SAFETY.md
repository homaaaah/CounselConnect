# Preserve behavior during UI changes

## When to use this checklist

Read this before redesigning, restructuring, or refactoring a data-driven interface, including its navigation, forms, modals, lists, hooks, and event handlers. Apply it to appointments, Counselor lists, resources, conversations, verification queues, SOS cases, and dashboards.

Follow [RULES.md](RULES.md) and the owning feature contract. This checklist does not authorize new behavior, broaden roles, or override the user's scope. Load only the relevant feature documentation and code.

## 1. Establish the behavior that must survive

Before editing:

- Inspect Git status and the diff; compare with the last known working version when available. Preserve unrelated work.
- Trace navigation through user selection, state, API requests, response processing, and the resulting display. Check the backend contract as well as the frontend.
- Record important invariants: record identity, available choices, pagination, date/time semantics, role/ownership checks, state transitions, and failure recovery.
- Identify the tests that verify those invariants. A successful build alone does not verify behavior.

For an implementation task, add this section to [CURRENT_TASK.md](CURRENT_TASK.md), alongside the normal objective and scope:

```markdown
## Contracts to preserve

| Invariant / user capability | Owning contract and code | Regression test |
|---|---|---|
| Selected record ID reaches the mutation unchanged | ... | ... |
| Choices beyond the first page remain reachable | ... | ... |

- Compatible API methods, paths, payload fields, and response shapes:
- Navigation and actions that must remain available:
- Required integration/browser checks and prerequisites:
- Intentional behavior changes explicitly authorized by the user:
```

Do not replace an invariant with whatever the current implementation happens to do. Resolve material conflicts using the project's authority order.

## 2. Know whether a list is complete

Every list consumer must answer: **Does the frontend currently have the complete result set?**

- If yes, identify the API guarantee or the verified completion condition for fetching all pages.
- If no, preserve pagination/load-more controls or query the specific records needed. Do not treat the first page as the complete list.
- Distinguish an empty complete result from a loading, failed, or partially loaded result. A failed later page must not silently become “no matching record.”
- Do not interpret the first `.find()` match as unique unless the API/database guarantees uniqueness or completeness has been established for the matching scope.
- Keep record IDs separate from display labels, formatted dates/times, names, and array positions.
- Preserve filters and accurate totals across pages. A backend total must describe the full filtered result, not just the current page length.

### Appointment example

A calendar time is only a display shortcut. It does not uniquely identify a Counselor, campus, or availability slot. Automatic selection requires exactly one matching loaded slot; this is not proof of global uniqueness when results are partial. Other matching choices must remain reachable, and selection must submit the intended `availability_slot_id` with a compatible `appointment_mode`.

Record this invariant in the owning [appointment contract](../docs/APPOINTMENT_SCHEDULING.md) when maintaining that behavior. A nearby comment should explain the non-obvious assumption, for example:

```js
// One calendar time can map to multiple slots.
// One API page may not contain the full day's availability.
```

Keep durable feature rules in their owning document and link to them here. Add concise code comments where an assumption can otherwise be lost during refactoring; do not duplicate the entire contract in each component.

## 3. Review logic changes as behavior changes

A layout-only refactor normally changes markup and styling. Explicitly review changes to:

- `.find()`, `.filter()`, `.map()`, sorting, grouping, and deduplication;
- fetch parameters, pagination, request payloads, and response envelopes;
- hooks, props, selection state, defaults, effect dependencies, and event handlers;
- routes, available actions/statuses, loading/error states, and permission gates.

These changes can alter behavior even when the task is described as “just a redesign.” Explain any intentional behavior change and preserve unrelated improvements.

Keep presentation and required logic changes separately reviewable; use separate commits when committing is authorized. Classify mixed work using the higher applicable risk level in [the workflow](../.kilo/rules/01-workflow.md). Follow its review requirements. This checklist does not grant permission to commit or push.

## 4. Test choices, identity, and failures

Use the actual component/hook and assert user-visible choices, selected IDs, request method/path/payload, and resulting state. Prefer accessible roles and labels over CSS classes or exact DOM nesting. If a redesign requires updating a selector, retain the behavioral assertion rather than deleting the test.

For each applicable silent-data-error case, add or retain a focused regression:

| Case | What to assert |
|---|---|
| Two records share a display name/date/time | Both are selectable; the chosen record ID is submitted |
| Needed record appears after page one | It is reachable and can be selected and submitted |
| Complete empty result | Correct empty state; no stale selection or mutation |
| Delayed or failed page/request | Loading/error is distinct from absence; no false uniqueness claim |
| Responses arrive out of order | Old responses cannot overwrite the latest filter or selection |
| Refresh follows a mutation | Selected status and displayed records agree; no stale refresh wins |
| Refresh changes choices | Preserve a still-valid selection/mode; invalidate an unavailable one |
| One independent data source fails | Unaffected records remain usable where the contract permits |
| Role, ownership, or status forbids an action | Frontend behavior and backend authorization remain correct |

Mocks must honor filters, pagination metadata, response fields, and relevant errors. Avoid a universal one-item response or unconditional successful mutations: those hide contract mismatches. Use synthetic data and isolated storage.

## 5. Verify the integrated flow

Run the affected frontend tests and build. For scheduling UI changes, also run the real React/API/MySQL integration before merge. From the repository root in Windows PowerShell, with dependencies installed:

```powershell
node --test frontend/tests/*.test.cjs
npm.cmd --prefix frontend run build
& ./backend/.venv/Scripts/python.exe -B -m pytest backend/app/tests/integration/test_appointments.py backend/app/tests/integration/test_appointments_frontend.py -q
```

The MySQL fixtures require `COUNSELCONNECT_TEST_DATABASE_URL`, a `mysql+pymysql` URL naming `counselconnect_test`, supplied securely in the environment. They create and remove their own disposable schemas. Never substitute the application database or print credentials.

`test_appointments_frontend.py` launches `frontend/tests/live-appointments.cjs` with a disposable backend, synthetic accounts, and the required environment variables. **Do not run that Node script bare against the normal app.** This harness uses React's test renderer, not a real browser.

When available, also run browser automation against isolated test data; otherwise manually check navigation, booking, Counselor review, status/history, cancellation, and rescheduling. Inspect console errors and network requests. Record exactly which checks ran, and distinguish browser testing from component/API integration.

Verify scripts and supported flags against the current checkout. It currently has no `backend/scripts/run_tests.py --browser` wrapper; do not copy a command from another revision without checking it. Skipped database tests or unavailable browser checks are verification gaps, never passes. Document missing prerequisites and complete the applicable checks before claiming integration is verified.

## 6. Final review and handoff

- [ ] Every preserved invariant has a code/contract reference and verifying test or explicit verification gap.
- [ ] Display labels are not used as unique identity without a contract guarantee.
- [ ] Partial lists, delayed responses, empty results, and failures behave correctly.
- [ ] API methods, paths, fields, enums, role scope, and ownership remain compatible.
- [ ] Required navigation, filters, actions, and history remain accessible.
- [ ] No behavioral tests were weakened merely to accommodate the new layout.
- [ ] Intentional behavior changes and their risk classification are visible in the diff/review.
- [ ] The completion report lists preserved invariants, exact checks/results, and remaining limitations.

Do not add a custom linter yet. Completeness and uniqueness depend on the data contract, not just syntax. Start with this review checklist and focused tests; consider automation only if repeated failures reveal a dependable rule.
