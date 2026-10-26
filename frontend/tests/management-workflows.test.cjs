const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const UsersPage = require("../src/pages/superadmin/UsersManagementPage.jsx").default;
const CorrectionsPage = require("../src/pages/superadmin/CorrectionsPage.jsx").default;
const StudentCorrections = require("../src/features/accounts/StudentCorrections.jsx").default;
const { RevisionForm } = require("../src/features/accounts/StudentCorrections.jsx");
const { PrivateCorPreview, usePagedRecords, useRecord, LoadState, Pagination } = require("../src/features/accounts/management.jsx");
const { ToastProvider } = require("../src/components/feedback");
const { setCsrfToken, setErrorHandler, setUnauthorizedHandler } = require("../src/services/apiClient.js");

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const now = "2026-10-25T12:00:00Z";
const summary = (id, role = "STUDENT") => ({ user_id: id, first_name: "Same", middle_name: null, last_name: "Person",
  email: `user${id}@example.edu`, role_code: role, account_status: "ACTIVE", is_deactivated: false, student_number: null, created_at: now, updated_at: now });
const requestRow = (id, version = 2, status = "PENDING") => ({ change_request_id: id, student_user_id: 8,
  submission_version: version, previous_change_request_id: null, root_change_request_id: null, status, created_at: now,
  requested_first_name: "Juan", requested_middle_name: null, requested_last_name: "Cruz", requested_year_level: 1, requested_section: "B" });
const current = { first_name: "Juan", middle_name: "Reyes", last_name: "Cruz", year_level: 1, section: "A" };
const studentDetail = (id, version = 2) => ({ change_request: requestRow(id, version, "RETURNED"), can_resubmit: true,
  registered_values_at_submission: version == null ? null : current, changed_fields: version == null ? null : ["section", "middle_name"],
  ...Object.fromEntries(Object.entries(current).map(([key, value]) => [`current_${key}`, value])) });
const reviewDetail = (id, version = 2) => ({ change_request: requestRow(id, version), student: summary(8),
  registered_values_at_submission: version == null ? null : current, extracted_values: version == null ? null : current,
  current_registered_values: current, proposed_changes: { section: "B" }, changed_fields: version == null ? null : ["section"],
  history: [requestRow(id, version)], evidence: { availability: version == null ? "LEGACY_UNKNOWN" : "AVAILABLE", expires_at: new Date(Date.now() + 60_000).toISOString() } });
const click = async (node) => act(async () => { await node.props.onClick(); });
const byText = (root, text) => root.root.findAllByType("button").find((node) => node.children.join("") === text);

function setup(t, fetch) {
  const savedWindow = global.window;
  global.window = { setTimeout, clearTimeout };
  t.mock.method(global, "fetch", fetch);
  setCsrfToken("synthetic-csrf"); setErrorHandler(null); setUnauthorizedHandler(null);
  t.after(() => { global.window = savedWindow; setCsrfToken(null); setErrorHandler(null); setUnauthorizedHandler(null); });
}
async function mount(t, component) {
  let root;
  await act(async () => { root = create(React.createElement(ToastProvider, null, component)); });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

test("Users page reaches page two and status confirmation retains identity with duplicate names", async (t) => {
  const users = Array.from({ length: 21 }, (_, index) => summary(index + 1, index === 20 ? "COUNSELOR" : "STUDENT"));
  const calls = [];
  setup(t, async (url, init = {}) => {
    calls.push({ url, init });
    const parsed = new URL(url, "http://test");
    const match = parsed.pathname.match(/\/accounts\/users\/(\d+)/);
    if (match) {
      const item = users[Number(match[1]) - 1];
      if (init.method === "POST") item.is_deactivated = parsed.pathname.endsWith("deactivate") && !parsed.pathname.endsWith("reactivate");
      return json({ ...item, profile: null, valid_until: null, password_hash: "PRIVATE-MUST-NOT-DISPLAY" });
    }
    const filtered = users.filter((item) => !parsed.searchParams.get("role_code") || item.role_code === parsed.searchParams.get("role_code"));
    const page = Number(parsed.searchParams.get("page"));
    return json({ items: filtered.slice((page - 1) * 20, page * 20), total: filtered.length });
  });
  const root = await mount(t, React.createElement(UsersPage, { user: summary(900, "SUPERADMIN") }));
  await click(byText(root, "Next"));
  await click(root.root.findByProps({ id: "user-open-21" }));
  assert.ok(!JSON.stringify(root.toJSON()).includes("PRIVATE-MUST-NOT-DISPLAY"));
  await click(root.root.findByProps({ id: "user-status-21" }));
  await click(byText(root, "Cancel"));
  assert.equal(calls.filter((call) => call.init.method === "POST").length, 0);
  await click(root.root.findByProps({ id: "user-status-21" }));
  await click(root.root.findByProps({ id: "confirm-user-status" }));
  const posted = calls.find((call) => call.init.method === "POST");
  assert.match(posted.url, /\/users\/21\/deactivate$/);
  assert.equal(posted.init.body, "{}");
  assert.equal(posted.init.credentials, "include");
  assert.equal(posted.init.headers["X-CSRF-Token"], "synthetic-csrf");
  await click(root.root.findByProps({ id: "user-status-21" }));
  await click(root.root.findByProps({ id: "confirm-user-status" }));
  assert.match(calls.filter((call) => call.init.method === "POST").at(-1).url, /\/21\/reactivate$/);
  await act(async () => root.root.findByProps({ "aria-label": "Role" }).props.onChange({ target: { value: "COUNSELOR" } }));
  assert.match(calls.at(-1).url, /page=1/);
  assert.match(calls.at(-1).url, /role_code=COUNSELOR/);
});

test("stale list and detail responses cannot overwrite newer choices", async (t) => {
  const pending = new Map();
  setup(t, (url) => new Promise((resolve) => pending.set(url, resolve)));
  let list, detail;
  function Harness() { list = usePagedRecords("/accounts/users", { q: "" }); detail = useRecord(list.filters.q ? `/accounts/users/${list.filters.q}` : null); return null; }
  await mount(t, React.createElement(Harness));
  const initial = [...pending.keys()][0];
  await act(async () => list.filter("q", "1"));
  const oldList = [...pending.keys()].find((url) => url.includes("q=1"));
  await act(async () => list.filter("q", "2"));
  const latest = [...pending.keys()].find((url) => url.includes("q=2"));
  await act(async () => { pending.get(latest)(json({ items: [summary(2)], total: 1 })); pending.get("/api/v1/accounts/users/2")(json(summary(2))); });
  await act(async () => { pending.get(initial)(json({ items: [], total: 0 })); pending.get(oldList)(json({ items: [summary(1)], total: 1 })); pending.get("/api/v1/accounts/users/1")(json(summary(1))); });
  assert.equal(list.items[0].user_id, 2);
  assert.equal(detail.data.user_id, 2);
});

for (const version of [5, null]) test(`review sends selected version ${version} and trimmed return reason`, async (t) => {
  const calls = [];
  let row = requestRow(77, version);
  setup(t, async (url, init = {}) => {
    calls.push({ url, init });
    if (init.method === "POST") { row = { ...row, status: "RETURNED" }; return json({ change_request: row }); }
    if (/\/77$/.test(url)) return json({ ...reviewDetail(77, version), change_request: row });
    return json({ items: row.status === "PENDING" ? [{ student: summary(8), change_request: row, changed_fields: version == null ? null : ["section"] }] : [], total: row.status === "PENDING" ? 1 : 0 });
  });
  const root = await mount(t, React.createElement(CorrectionsPage));
  await click(root.root.findByProps({ id: "review-open-77" }));
  assert.equal(root.root.findByProps({ id: "review-approve-77" }).props.disabled, version === null);
  await click(root.root.findByProps({ id: "review-return-77" }));
  assert.equal(root.root.findByProps({ id: "confirm-correction-decision" }).props.disabled, true);
  await act(async () => root.root.findByProps({ "aria-label": "Return reason" }).props.onChange({ target: { value: "  Check the section.  " } }));
  assert.equal(root.root.findByProps({ "aria-label": "Return reason" }).props.maxLength, 500);
  await click(root.root.findByProps({ id: "confirm-correction-decision" }));
  const posted = calls.find((call) => call.init.method === "POST");
  assert.match(posted.url, /\/77\/return$/);
  assert.deepEqual(JSON.parse(posted.init.body), { submission_version: version, reason: "Check the section." });
});

for (const version of [3, null]) test(`Student revision sends real multipart and preserved version ${version}`, async (t) => {
  let posted, newId;
  setup(t, async (url, init) => { posted = { url, init }; return json({ change_request: requestRow(99, 4) }, 201); });
  const root = await mount(t, React.createElement(RevisionForm, { detail: studentDetail(42, version), onSubmitted: (id) => { newId = id; } }));
  await act(async () => root.root.findByProps({ "aria-label": "Middle name" }).props.onChange({ target: { value: "" } }));
  await act(async () => root.root.findByProps({ "aria-label": "Year level" }).props.onChange({ target: { value: "10" } }));
  const file = new File(["%PDF-1.4 fresh"], "current.pdf", { type: "application/pdf" });
  await act(async () => root.root.findByProps({ "aria-label": "Fresh current COR PDF" }).props.onChange({ target: { files: [file] } }));
  await act(async () => root.root.findByType("form").props.onSubmit({ preventDefault() {} }));
  assert.match(posted.url, /\/42\/resubmit$/);
  assert.equal(posted.init.body.get("submission_version"), version == null ? "null" : "3");
  assert.equal(posted.init.body.get("file").name, "current.pdf");
  assert.equal(JSON.parse(posted.init.body.get("proposed_changes")).middle_name, null);
  assert.equal(JSON.parse(posted.init.body.get("proposed_changes")).year_level, 10);
  assert.equal(new Headers(posted.init.headers).has("Content-Type"), false);
  assert.equal(posted.init.headers["X-CSRF-Token"], "synthetic-csrf");
  assert.equal(newId, 99);
});

test("Student statuses show current/proposed separation and paged history", async (t) => {
  setup(t, async (url) => {
    if (/\/42$/.test(url)) return json(studentDetail(42, null));
    return json({ items: [studentDetail(42, null)], total: 21 });
  });
  const root = await mount(t, React.createElement(StudentCorrections, { user: summary(8) }));
  assert.equal(byText(root, "Next").props.disabled, false);
  await click(root.root.findByProps({ id: "my-correction-42" }));
  const rendered = JSON.stringify(root.toJSON());
  assert.match(rendered, /Historical comparison unavailable/);
  assert.match(rendered, /Current registered/);
  assert.match(rendered, /fresh current COR PDF/i);
});

test("private preview uses authenticated no-store blob fetch and releases every URL", async (t) => {
  const revoked = [];
  let sequence = 0, fetched;
  t.mock.method(URL, "createObjectURL", () => `blob:private-${++sequence}`);
  t.mock.method(URL, "revokeObjectURL", (url) => revoked.push(url));
  setup(t, async (url, init) => { fetched = { url, init }; return new Response("%PDF-1.4", { headers: { "Content-Type": "application/pdf" } }); });
  const evidence = { availability: "AVAILABLE", expires_at: new Date(Date.now() + 60_000).toISOString() };
  const root = await mount(t, React.createElement(PrivateCorPreview, { id: 7, evidence }));
  await click(byText(root, "Preview current COR"));
  assert.equal(fetched.init.credentials, "include"); assert.equal(fetched.init.cache, "no-store");
  assert.match(fetched.url, /\/7\/cor$/);
  assert.equal(root.root.findByType("iframe").props.src, "blob:private-1");
  await click(byText(root, "Close preview"));
  assert.deepEqual(revoked, ["blob:private-1"]);
  await click(byText(root, "Preview current COR"));
  await act(async () => root.unmount());
  assert.deepEqual(revoked, ["blob:private-1", "blob:private-2"]);
});

test("page load failure is recoverable and does not masquerade as a complete empty list", async (t) => {
  let failed = true, state;
  setup(t, async () => failed ? json({ error: { code: "TEMPORARY", message: "Try again." } }, 503) : json({ items: [summary(9)], total: 1 }));
  function Harness() { state = usePagedRecords("/accounts/users"); return React.createElement(React.Fragment, null,
    React.createElement(LoadState, { state }), React.createElement(Pagination, { state })); }
  const root = await mount(t, React.createElement(Harness));
  assert.equal(state.error, "Try again."); assert.equal(state.loading, false);
  assert.ok(!JSON.stringify(root.toJSON()).includes("0 records"));
  failed = false;
  await click(byText(root, "Retry"));
  assert.equal(state.error, ""); assert.equal(state.items[0].user_id, 9);
});

test("private preview revokes URLs on identity changes and ignores a late fetch after unmount", async (t) => {
  const revoked = []; let creates = 0, resolveFetch;
  t.mock.method(URL, "createObjectURL", () => `blob:owned-${++creates}`);
  t.mock.method(URL, "revokeObjectURL", (url) => revoked.push(url));
  let deferred = false;
  setup(t, async () => deferred ? new Promise((resolve) => { resolveFetch = resolve; }) : new Response("%PDF", { headers: { "Content-Type": "application/pdf" } }));
  const evidence = { availability: "AVAILABLE", expires_at: new Date(Date.now() + 60_000).toISOString() };
  const root = await mount(t, React.createElement(PrivateCorPreview, { id: 1, evidence }));
  await click(byText(root, "Preview current COR"));
  await act(async () => root.update(React.createElement(ToastProvider, null, React.createElement(PrivateCorPreview, { id: 2, evidence }))));
  assert.deepEqual(revoked, ["blob:owned-1"]);
  deferred = true;
  let loading;
  await act(async () => { loading = byText(root, "Preview current COR").props.onClick(); });
  await act(async () => root.unmount());
  await act(async () => { resolveFetch(new Response("%PDF")); await loading; });
  assert.equal(creates, 1);
});

test("expired preview is released and private error details are not rendered", async (t) => {
  const revoked = [];
  t.mock.method(URL, "createObjectURL", () => "blob:expires");
  t.mock.method(URL, "revokeObjectURL", (url) => revoked.push(url));
  let fail = false;
  setup(t, async () => fail ? json({ error: { code: "COR_EVIDENCE_UNAVAILABLE", message: "Evidence unavailable.", details: { path: "PRIVATE-PATH" } } }, 409) : new Response("%PDF"));
  const evidence = { availability: "AVAILABLE", expires_at: new Date(Date.now() + 100).toISOString() };
  const root = await mount(t, React.createElement(PrivateCorPreview, { id: 1, evidence }));
  await click(byText(root, "Preview current COR"));
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 115)); });
  assert.deepEqual(revoked, ["blob:expires"]);
  assert.equal(root.root.findAllByType("iframe").length, 0);
  assert.equal(byText(root, "Preview current COR").props.disabled, true);
  fail = true;
  await act(async () => root.update(React.createElement(ToastProvider, null, React.createElement(PrivateCorPreview, { id: 2, evidence: { ...evidence, expires_at: new Date(Date.now() + 60_000).toISOString() } }))));
  await click(byText(root, "Preview current COR"));
  assert.match(JSON.stringify(root.toJSON()), /Evidence unavailable/);
  assert.ok(!JSON.stringify(root.toJSON()).includes("PRIVATE-PATH"));
});

test("stale approval conflicts reload exact detail and cannot silently apply a later version", async (t) => {
  const calls = []; let conflicts = false;
  setup(t, async (url, init = {}) => {
    calls.push({ url, init });
    if (init.method === "POST") { conflicts = true; return json({ error: { code: "CHANGE_REQUEST_VERSION_CONFLICT", message: "Version changed." } }, 409); }
    if (/\/88$/.test(url)) return json(reviewDetail(88, conflicts ? 4 : 3));
    return json({ items: [{ student: summary(8), change_request: requestRow(88, 3), changed_fields: ["section"] }], total: 1 });
  });
  const root = await mount(t, React.createElement(CorrectionsPage));
  await click(root.root.findByProps({ id: "review-open-88" }));
  await click(root.root.findByProps({ id: "review-approve-88" }));
  await click(root.root.findByProps({ id: "confirm-correction-decision" }));
  assert.deepEqual(JSON.parse(calls.find((call) => call.init.method === "POST").init.body), { submission_version: 3 });
  assert.match(JSON.stringify(root.toJSON()), /Version changed/);
  assert.ok(calls.filter((call) => /\/88$/.test(call.url)).length >= 2);
  assert.equal(root.root.findAllByProps({ id: "confirm-correction-decision" }).length, 0);
});

test("protected role has no status action and failed revisions retain editable input", async (t) => {
  setup(t, async (url) => /\/users\/9$/.test(url) ? json({ ...summary(9, "SUPERADMIN"), profile: null }) : json({ items: [summary(9, "SUPERADMIN")], total: 1 }));
  const root = await mount(t, React.createElement(UsersPage, { user: summary(900, "SUPERADMIN") }));
  await click(root.root.findByProps({ id: "user-open-9" }));
  assert.equal(root.root.findAllByProps({ id: "user-status-9" }).length, 0);
  global.fetch = async () => json({ error: { code: "NO_CORRECTION_CHANGES", message: "Change at least one field." } }, 422);
  let submitted = false;
  const form = await mount(t, React.createElement(RevisionForm, { detail: studentDetail(42), onSubmitted: () => { submitted = true; } }));
  const file = new File(["%PDF"], "fresh.pdf", { type: "application/pdf" });
  await act(async () => form.root.findByProps({ "aria-label": "Fresh current COR PDF" }).props.onChange({ target: { files: [file] } }));
  await act(async () => form.root.findByType("form").props.onSubmit({ preventDefault() {} }));
  assert.equal(submitted, false);
  assert.equal(form.root.findByProps({ "aria-label": "Middle name" }).props.value, "Reyes");
  assert.match(JSON.stringify(form.toJSON()), /Change at least one field/);
});
