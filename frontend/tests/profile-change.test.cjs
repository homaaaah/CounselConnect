const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");
const { setCsrfToken } = require("../src/services/apiClient.js");
const CounselorUsersPage = require("../src/pages/counselor/CounselorUsersPage.jsx").default;
const { ToastProvider } = require("../src/components/feedback/Notifications.jsx");

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

function pendingItem() {
  return {
    change_request: {
      change_request_id: 7,
      student_user_id: 2,
      cor_screening_id: 1,
      status: "PENDING",
      requested_first_name: "Ana",
      requested_middle_name: null,
      requested_last_name: "Reyes",
      requested_year_level: 2,
      requested_section: "B",
      reviewed_by_user_id: null,
      reviewed_at: null,
      decision_reason: null,
      created_at: "2026-10-01T10:00:00Z",
    },
    student: {
      user_id: 2,
      email: "ana@example.edu",
      first_name: "Ana",
      middle_name: null,
      last_name: "Santos",
      account_status: "ACTIVE",
    },
    current_first_name: "Ana",
    current_middle_name: null,
    current_last_name: "Santos",
    current_year_level: 1,
    current_section: "A",
  };
}

function setup(t, { pending = [pendingItem()] } = {}) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const parsed = new URL(url, "http://localhost:5173");
    calls.push({ path: parsed.pathname, search: parsed.search, ...init });
    if (parsed.pathname === "/api/v1/profile-change-requests") {
      return json({ items: pending, page: 1, page_size: 20, total: pending.length });
    }
    if (parsed.pathname === "/api/v1/accounts/students") {
      return json({ items: [], page: 1, page_size: 20, total: 0 });
    }
    if (parsed.pathname === "/api/v1/accounts/campuses") return json({ items: [] });
    if (parsed.pathname === "/api/v1/accounts/programs") return json({ items: [] });
    return json({});
  });
  return calls;
}

async function mount(t, props = { canRecover: true }) {
  let root;
  await act(async () => {
    root = create(
      React.createElement(ToastProvider, null, React.createElement(CounselorUsersPage, props)),
    );
  });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (predicate()) return;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
  }
  throw new Error("UI did not reach the expected state");
}

const hasId = (root, id) => root.root.findAllByProps({ id }).length > 0;

test("superadmin sees pending edit requests and approves one", async (t) => {
  setCsrfToken("synthetic-csrf");
  const calls = setup(t);
  const root = await mount(t);
  await waitFor(() => hasId(root, "edit-approve-7"));

  const rendered = JSON.stringify(root.toJSON());
  assert.match(rendered, /Pending edit requests/);
  assert.match(rendered, /Santos/);
  assert.match(rendered, /Reyes/);

  await act(async () => { await root.root.findByProps({ id: "edit-approve-7" }).props.onClick(); });
  const approve = calls.find((call) => call.path === "/api/v1/profile-change-requests/7/approve");
  assert.ok(approve, "approve posts to the approve endpoint");
  assert.equal(approve.method, "POST");
  setCsrfToken(null);
});

test("superadmin rejects with a required reason", async (t) => {
  setCsrfToken("synthetic-csrf");
  const calls = setup(t);
  const root = await mount(t);
  await waitFor(() => hasId(root, "edit-reject-7"));

  await act(async () => { root.root.findByProps({ id: "edit-reject-7" }).props.onClick(); });
  await act(async () => {
    root.root.findByProps({ id: "edit-reason-7" }).props.onChange({ target: { value: "Blurry COR" } });
  });
  await act(async () => {
    await root.root.findByProps({ id: "edit-reject-confirm-7" }).props.onClick();
  });

  const reject = calls.find((call) => call.path === "/api/v1/profile-change-requests/7/reject");
  assert.ok(reject, "reject posts to the reject endpoint");
  assert.equal(JSON.parse(reject.body).reason, "Blurry COR");
  setCsrfToken(null);
});

test("counselor view hides the pending edit queue", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t);
  const root = await mount(t, { canRecover: false });
  await waitFor(() => root.root.findAllByType("table").length > 0);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Pending edit requests"));
  assert.equal(hasId(root, "edit-approve-7"), false);
  setCsrfToken(null);
});
