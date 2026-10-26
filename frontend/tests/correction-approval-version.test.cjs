const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const { useProfileChangeRequests } = require("../src/features/accounts/useProfileChangeRequests.js");
const { setCsrfToken } = require("../src/services/apiClient.js");

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

test("approval sends the displayed version and session CSRF through the real API client", async (t) => {
  let state;
  let posted;
  const originalFetch = global.fetch;
  t.after(() => { global.fetch = originalFetch; setCsrfToken(null); });
  setCsrfToken("test-csrf");
  global.fetch = async (url, options = {}) => {
    if (options.method === "POST") {
      posted = { url, options };
      return json({ change_request: { change_request_id: 73, submission_version: 4, status: "APPROVED" },
        current_registered_values: { section: "B" }, registered_values_at_submission: { section: "A" },
        proposed_changes: { section: "B" }, changed_fields: ["section"], evidence: { availability: "RESOLVED", expires_at: null } });
    }
    return json({ items: [{ change_request: { change_request_id: 73, submission_version: 4 } }], total: 1 });
  };
  function Harness() { state = useProfileChangeRequests(); return null; }
  let root;
  await act(async () => { root = create(React.createElement(Harness)); });
  t.after(async () => { await act(async () => root.unmount()); });
  const row = state.items[0].change_request;
  let result;
  await act(async () => { result = await state.approve(row.change_request_id, row.submission_version); });
  assert.equal(result.success, true);
  assert.match(posted.url, /\/profile-change-requests\/73\/approve$/);
  assert.deepEqual(JSON.parse(posted.options.body), { submission_version: 4 });
  assert.equal(new Headers(posted.options.headers).get("X-CSRF-Token"), "test-csrf");
});

test("queue buttons retain record identity/version and disable unknown legacy approval", async (t) => {
  const CounselorUsersPage = require("../src/pages/counselor/CounselorUsersPage.jsx").default;
  const { ToastProvider } = require("../src/components/feedback");
  const originalFetch = global.fetch;
  const originalWindow = global.window;
  global.window = { setTimeout, clearTimeout };
  t.after(() => { global.fetch = originalFetch; global.window = originalWindow; setCsrfToken(null); });
  setCsrfToken("queue-csrf");
  const posted = [];
  const row = (id, version) => ({
    change_request: { change_request_id: id, submission_version: version, requested_first_name: "Juan",
      requested_last_name: "Cruz", requested_middle_name: null, requested_year_level: 1, requested_section: "B" },
    student: { user_id: id + 100, first_name: "Juan", last_name: "Cruz", email: `student${id}@example.edu` },
    current_first_name: "Juan", current_last_name: "Cruz", current_year_level: 1, current_section: "A",
  });
  global.fetch = async (url, options = {}) => {
    if (options.method === "POST") { posted.push({ url, options });
      return json({ change_request: { change_request_id: 92, submission_version: 7, status: "APPROVED" },
        current_registered_values: { section: "B" }, evidence: { availability: "RESOLVED", expires_at: null } }); }
    if (url.includes("/profile-change-requests")) return json({ items: [row(73, 4), row(92, 7), row(88, null)], total: 3 });
    return json({ items: [], total: 0 });
  };
  let root;
  await act(async () => { root = create(React.createElement(ToastProvider, null,
    React.createElement(CounselorUsersPage, { canRecover: true }))); });
  t.after(async () => { await act(async () => root.unmount()); });
  assert.equal(root.root.findByProps({ id: "edit-approve-88" }).props.disabled, true);
  assert.equal(root.root.findByProps({ id: "edit-approve-92" }).props.disabled, false);
  await act(async () => { await root.root.findByProps({ id: "edit-approve-92" }).props.onClick(); });
  assert.equal(posted.length, 1);
  assert.match(posted[0].url, /\/profile-change-requests\/92\/approve$/);
  assert.deepEqual(JSON.parse(posted[0].options.body), { submission_version: 7 });
});

for (const version of [3, null]) {
  test(`queue return sends clicked ID/version ${version} and trimmed reason without exposing it in toasts`, async (t) => {
    const CounselorUsersPage = require("../src/pages/counselor/CounselorUsersPage.jsx").default;
    const { ToastProvider } = require("../src/components/feedback");
    const originalFetch = global.fetch;
    t.after(() => { global.fetch = originalFetch; setCsrfToken(null); });
    setCsrfToken("return-csrf");
    const targetId = version === null ? 88 : 92;
    let posted;
    let completed = false;
    const row = (id, submissionVersion) => ({
      change_request: { change_request_id: id, submission_version: submissionVersion, requested_first_name: "Juan",
        requested_last_name: "Cruz", requested_year_level: 1, requested_section: "B" },
      student: { user_id: id + 100, first_name: "Juan", last_name: "Cruz", email: `student${id}@example.edu` },
      current_first_name: "Juan", current_last_name: "Cruz", current_year_level: 1, current_section: "A",
    });
    global.fetch = async (url, options = {}) => {
      if (options.method === "POST") {
        posted = { url, options };
        completed = true;
        return json({ change_request: { change_request_id: targetId, submission_version: version, status: "RETURNED" },
          evidence: { availability: "RESOLVED", expires_at: null } });
      }
      if (url.includes("/profile-change-requests")) {
        assert.match(url, /status=PENDING/);
        return json({ items: [row(73, 4), ...(completed ? [] : [row(targetId, version)])], total: completed ? 1 : 2 });
      }
      return json({ items: [], total: 0 });
    };
    let root;
    await act(async () => { root = create(React.createElement(ToastProvider, null,
      React.createElement(CounselorUsersPage, { canRecover: true }))); });
    t.after(async () => { await act(async () => root.unmount()); });
    const open = root.root.findByProps({ id: `edit-reject-${targetId}` });
    assert.equal(open.children.join(""), "Return");
    await act(async () => { open.props.onClick(); });
    const confirmId = `edit-reject-confirm-${targetId}`;
    assert.equal(root.root.findByProps({ id: confirmId }).children.join(""), "Confirm return");
    await act(async () => { await root.root.findByProps({ id: confirmId }).props.onClick(); });
    assert.equal(posted, undefined); // blank reason is blocked locally
    const input = root.root.findByProps({ id: `edit-reason-${targetId}` });
    assert.equal(input.props.maxLength, 500);
    await act(async () => { input.props.onChange({ target: { value: "  Please fix the section.  " } }); });
    await act(async () => { await root.root.findByProps({ id: confirmId }).props.onClick(); });
    assert.match(posted.url, new RegExp(`/profile-change-requests/${targetId}/return$`));
    assert.deepEqual(JSON.parse(posted.options.body), { submission_version: version, reason: "Please fix the section." });
    assert.equal(new Headers(posted.options.headers).get("X-CSRF-Token"), "return-csrf");
    assert.equal(root.root.findAllByProps({ id: `edit-reject-${targetId}` }).length, 0);
    assert.equal(root.root.findAllByProps({ id: "edit-reject-73" }).length, 1);
    assert.ok(!JSON.stringify(root.toJSON()).includes("Please fix the section."));
  });
}
