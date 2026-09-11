const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const App = require("../src/App.jsx").default;
const { setCsrfToken, getCsrfToken, request } = require("../src/services/apiClient.js");
const { useReviewerConsole } = require("../src/features/enrollment/useReviewerConsole.js");

const auth = {
  user: { user_id: 1, email: "counselor@example.edu", role_code: "COUNSELOR",
    account_status: "ACTIVE", first_name: "Cora", last_name: "Reyes" },
  csrf_token: "synthetic-csrf-token", idle_expires_at: "2099-01-01T01:00:00Z",
  absolute_expires_at: "2099-01-01T12:00:00Z",
};
const application = {
  verification: { verification_id: 7, status: "PENDING", submitted_at: "2026-09-06T00:00:00Z" },
  student: { user_id: 2, first_name: "Ana", last_name: "Santos", email: "student@example.edu" },
  file: null,
};
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const failure = (status) => json({ error: { code: "TEST_ERROR", message: "Test error" } }, status);

function environment(t, initialHash = "#review") {
  const events = new EventTarget();
  let hash = initialHash;
  const location = { reload: t.mock.fn() };
  Object.defineProperty(location, "hash", {
    get: () => hash,
    set: (value) => { hash = value; events.dispatchEvent(new Event("hashchange")); },
  });
  global.window = { location, open: t.mock.fn(),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events) };
  setCsrfToken(null);
  t.after(() => { setCsrfToken(null); });
}

function fakeApi(t, recover = () => json(auth)) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    calls.push({ path: new URL(url).pathname, ...init });
    if (url.endsWith("/auth/csrf")) return recover();
    if (url.endsWith("/auth/login")) return json(auth);
    if (url.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (url.endsWith("/pending")) return json([application]);
    if (url.endsWith("/history")) return json([]);
    if (url.endsWith("/approve")) return json({ email_queued: false });
    if (url.endsWith("/health")) return json({ status: "ok" });
    if (url.endsWith("/cor")) return new Response("%PDF-test");
    return json({ items: [] });
  });
  return calls;
}

async function mount(t, component = React.createElement(App)) {
  let root;
  await act(async () => { root = create(component); });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

test("student login link opens the staff email form and switches back", async (t) => {
  environment(t, "#login");
  fakeApi(t, () => failure(401));
  const root = await mount(t);
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Student number");
  const staffLink = root.root.findByProps({ href: "#staff-login" });
  await act(async () => { window.location.hash = staffLink.props.href; });
  assert.equal(root.root.findByType("h1").children.join(""), "Counselor / Staff sign in");
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Email");
  assert.equal(root.root.findByProps({ id: "identifier" }).props.type, "email");
  await act(async () => { window.location.hash = "#login"; });
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Student number");
});

test("reload waits for CSRF recovery before loading the reviewer and approving", async (t) => {
  environment(t);
  let resolve;
  const recovery = new Promise((done) => { resolve = done; });
  const calls = fakeApi(t, () => recovery);
  const root = await mount(t);
  assert.match(JSON.stringify(root.toJSON()), /Restoring your session/);
  assert.equal(calls.some((call) => call.path.includes("enrollment-verifications")), false);
  await act(async () => { resolve(json(auth)); });
  const approve = root.root.findAllByType("button").find((button) => button.children.includes("Approve"));
  assert.ok(approve);
  await act(async () => { await approve.props.onClick(); });
  const sent = calls.find((call) => call.path.endsWith("/approve"));
  assert.equal(sent.headers["X-CSRF-Token"], auth.csrf_token);
  assert.equal(sent.credentials, "include");
});

test("login reaches the reviewer without a page reload or loss of CSRF", async (t) => {
  environment(t, "#login");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  fakeApi(t, () => failure(401));
  const root = await mount(t);
  await act(async () => {
    root.root.findByProps({ id: "identifier" }).props.onChange({ target: { value: "counselor@example.edu" } });
    root.root.findByProps({ id: "password" }).props.onChange({ target: { value: "synthetic-password" } });
  });
  await act(async () => { await root.root.findByType("form").props.onSubmit({ preventDefault() {} }); });
  await act(async () => { t.mock.timers.tick(700); });
  assert.match(JSON.stringify(root.toJSON()), /Registration review/);
  assert.equal(window.location.reload.mock.callCount(), 0);
  assert.equal(getCsrfToken(), auth.csrf_token);
});

test("failed session recovery never loads confidential review data", async (t) => {
  environment(t);
  const calls = fakeApi(t, () => failure(500));
  const root = await mount(t);
  assert.match(JSON.stringify(root.toJSON()), /Could not restore your session/);
  assert.equal(calls.some((call) => call.path.includes("enrollment-verifications")), false);
  assert.equal(getCsrfToken(), null);
});

test("a Student cannot mount the reviewer console", async (t) => {
  environment(t);
  const calls = fakeApi(t, () => json({ ...auth, user: { ...auth.user, role_code: "STUDENT" } }));
  const root = await mount(t);
  assert.match(JSON.stringify(root.toJSON()), /requires a Counselor account/);
  assert.equal(calls.some((call) => call.path.includes("enrollment-verifications")), false);
});

test("sign out uses recovered CSRF and clears the protected page", async (t) => {
  environment(t);
  const calls = fakeApi(t);
  const root = await mount(t);
  const logout = root.root.findAllByType("button").find((button) => button.children.includes("Sign out"));
  await act(async () => { await logout.props.onClick(); });
  assert.equal(calls.find((call) => call.path.endsWith("/logout")).headers["X-CSRF-Token"], auth.csrf_token);
  assert.equal(getCsrfToken(), null);
  assert.doesNotMatch(JSON.stringify(root.toJSON()), /Registration review/);
});

test("a late unauthenticated response cannot erase a newer login token", async (t) => {
  environment(t);
  let resolve;
  t.mock.method(global, "fetch", () => new Promise((done) => { resolve = done; }));
  const pending = request("/auth/csrf").catch(() => {});
  setCsrfToken(auth.csrf_token);
  resolve(failure(401));
  await pending;
  assert.equal(getCsrfToken(), auth.csrf_token);
});

test("COR preview blobs are released when the reviewer unmounts", async (t) => {
  environment(t);
  fakeApi(t);
  const createUrl = t.mock.method(URL, "createObjectURL", () => "blob:synthetic-cor");
  const revokeUrl = t.mock.method(URL, "revokeObjectURL", () => {});
  let reviewer;
  function Harness() { reviewer = useReviewerConsole(); return null; }
  const root = await mount(t, React.createElement(Harness));
  await act(async () => { await reviewer.openCorPdf(7); });
  assert.equal(createUrl.mock.callCount(), 1);
  await act(async () => root.unmount());
  assert.equal(revokeUrl.mock.calls[0].arguments[0], "blob:synthetic-cor");
});

test("a preview still downloading at decision time is discarded", async (t) => {
  environment(t);
  fakeApi(t);
  const previousFetch = global.fetch;
  let resolvePdf;
  t.mock.method(global, "fetch", (url, init) => url.endsWith("/cor")
    ? new Promise((resolve) => { resolvePdf = resolve; }) : previousFetch(url, init));
  const createUrl = t.mock.method(URL, "createObjectURL", () => "blob:should-not-be-created");
  let reviewer;
  function Harness() { reviewer = useReviewerConsole(); return null; }
  await mount(t, React.createElement(Harness));
  const pendingPreview = reviewer.openCorPdf(7);
  await act(async () => { await reviewer.approve(7); });
  await act(async () => { resolvePdf(new Response("%PDF-test")); await pendingPreview; });
  assert.equal(createUrl.mock.callCount(), 0);
});
