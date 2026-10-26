const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const UsersPage = require("../src/pages/superadmin/UsersManagementPage.jsx").default;
const { ToastProvider } = require("../src/components/feedback");
const { setCsrfToken, setErrorHandler, setUnauthorizedHandler } = require("../src/services/apiClient");
const stamp = "2026-10-26T01:02:03.123456Z";
const person = id => ({ user_id: id, email: `counselor-${id}@example.edu`, first_name: "Same", middle_name: null,
  last_name: "Name", role_code: "COUNSELOR", account_status: "ACTIVE", is_deactivated: false,
  created_at: stamp, updated_at: stamp, profile: null, student_number: null });
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const button = (root, title) => root.root.findAllByType("button").find(node => node.children.join("") === title);
const click = node => act(async () => node.props.onClick());
const change = (root, id, value) => act(async () => root.root.findByProps({ id }).props.onChange({ target: { value } }));
async function mount(t, fetch) {
  const previous = global.window;
  global.window = { setTimeout, clearTimeout };
  t.mock.method(global, "fetch", fetch);
  setCsrfToken("counselor-csrf"); setErrorHandler(null); setUnauthorizedHandler(null);
  let root;
  await act(async () => { root = create(React.createElement(ToastProvider, null, React.createElement(UsersPage, { user: { user_id: 900, role_code: "SUPERADMIN" } }))); });
  t.after(async () => { await act(async () => root.unmount()); global.window = previous; setCsrfToken(null); });
  return root;
}

test("create Counselor posts strict credentials and opens the returned account ID", async t => {
  const calls = [];
  const row = person(44);
  const root = await mount(t, async (url, init = {}) => {
    calls.push({ url, init });
    if (init.method === "POST") return json(row, 201);
    if (url.endsWith("/44")) return json(row);
    return json({ items: [], total: 0 });
  });
  await click(button(root, "Create Counselor"));
  await change(root, "counselor-first_name", "New");
  await change(root, "counselor-last_name", "Counselor");
  await change(root, "counselor-email", "new@example.edu");
  await change(root, "counselor-password", "initial-password");
  await change(root, "counselor-confirm-password", "initial-password");
  const form = root.root.findByProps({ "aria-label": "Create counselor account" });
  assert.equal(root.root.findByProps({ id: "counselor-password" }).props.type, "password");
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const call = calls.find(item => item.init.method === "POST");
  assert.equal(call.url, "/api/v1/accounts/users");
  assert.equal(call.init.headers["X-CSRF-Token"], "counselor-csrf");
  assert.deepEqual(JSON.parse(call.init.body), { first_name: "New", middle_name: null, last_name: "Counselor", email: "new@example.edu", password: "initial-password" });
  assert.equal(root.root.findAllByProps({ id: "counselor-password" }).length, 0, "Success unmounts the credential form");
  assert.ok(calls.some(item => item.url.endsWith("/44")));
  assert.ok(root.root.findByProps({ id: "counselor-edit-44" }));
});

test("edit uses selected ID and displayed timestamp, never credentials or role", async t => {
  const calls = [];
  const row = person(22);
  const root = await mount(t, async (url, init = {}) => {
    calls.push({ url, init });
    if (init.method === "PATCH") return json({ ...row, first_name: "Changed" });
    if (url.endsWith("/22")) return json(row);
    return json({ items: [person(21), row], total: 2 });
  });
  await click(root.root.findByProps({ id: "user-open-22" }));
  await click(root.root.findByProps({ id: "counselor-edit-22" }));
  assert.equal(root.root.findAllByProps({ id: "counselor-password" }).length, 0);
  await change(root, "counselor-first_name", "Changed");
  const form = root.root.findByProps({ "aria-label": "Edit counselor account" });
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const call = calls.find(item => item.init.method === "PATCH");
  assert.equal(call.url, "/api/v1/accounts/users/22");
  assert.deepEqual(JSON.parse(call.init.body), { first_name: "Changed", middle_name: null, last_name: "Name", email: row.email, expected_updated_at: stamp });
});

test("password mismatch and cancellation do not create an account", async t => {
  const mutations = [];
  const root = await mount(t, async (url, init = {}) => { if (init.method) mutations.push(init); return json({ items: [], total: 0 }); });
  await click(button(root, "Create Counselor"));
  await change(root, "counselor-password", "first-password");
  await change(root, "counselor-confirm-password", "different-password");
  await act(async () => root.root.findByProps({ "aria-label": "Create counselor account" }).props.onSubmit({ preventDefault() {} }));
  assert.match(JSON.stringify(root.toJSON()), /passwords do not match/);
  await click(button(root, "Cancel"));
  assert.equal(root.root.findAllByProps({ id: "counselor-password" }).length, 0);
  assert.equal(mutations.length, 0);
});

test("stale edit remains visible with input retained and cannot silently retry a new timestamp", async t => {
  const row = person(22);
  const patches = [];
  const root = await mount(t, async (url, init = {}) => {
    if (init.method === "PATCH") { patches.push(JSON.parse(init.body)); return json({ error: { code: "USER_EDIT_CONFLICT", message: "This account has changed. Reload its details before saving." } }, 409); }
    return json(url.endsWith("/22") ? row : { items: [row], total: 1 });
  });
  await click(root.root.findByProps({ id: "user-open-22" }));
  await click(root.root.findByProps({ id: "counselor-edit-22" }));
  await change(root, "counselor-email", "changed@example.edu");
  await act(async () => root.root.findByProps({ "aria-label": "Edit counselor account" }).props.onSubmit({ preventDefault() {} }));
  assert.equal(root.root.findByProps({ id: "counselor-email" }).props.value, "changed@example.edu");
  assert.match(JSON.stringify(root.toJSON()), /Reload its details/);
  assert.equal(patches.length, 1);
  assert.equal(patches[0].expected_updated_at, stamp);
});

test("non-Counselor details never expose the edit action", async t => {
  const row = { ...person(22), role_code: "STUDENT" };
  const root = await mount(t, async url => json(url.endsWith("/22") ? row : { items: [row], total: 1 }));
  await click(root.root.findByProps({ id: "user-open-22" }));
  assert.equal(root.root.findAllByProps({ id: "counselor-edit-22" }).length, 0);
});
