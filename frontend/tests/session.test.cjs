const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const App = require("../src/App.jsx").default;
const { setCsrfToken, getCsrfToken, request, ApiError } = require("../src/services/apiClient.js");

const auth = {
  user: { user_id: 1, email: "counselor@example.edu", role_code: "COUNSELOR",
    account_status: "ACTIVE", first_name: "Cora", last_name: "Reyes" },
  csrf_token: "synthetic-csrf-token", idle_expires_at: "2099-01-01T01:00:00Z",
  absolute_expires_at: "2099-01-01T12:00:00Z",
};
const studentAuth = {
  user: { user_id: 2, email: "student@example.edu", role_code: "STUDENT",
    account_status: "PENDING_VERIFICATION", first_name: "Ana", last_name: "Santos" },
  csrf_token: "synthetic-csrf-token", idle_expires_at: "2099-01-01T01:00:00Z",
  absolute_expires_at: "2099-01-01T12:00:00Z",
};
const screening = {
  cor_screening_id: 7, student_user_id: 2, status: "AWAITING_CONFIRMATION",
  format_template_version: "ucc-registration-v1", format_match_score: 0.9,
  extraction_confidence: 0.9, barcode_status: "DECODED", barcode_symbology: "QR_CODE",
  failure_reason_code: null, extracted_student_number: "20231234-A",
  extracted_first_name: "Ana", extracted_middle_name: null, extracted_last_name: "Santos",
  extracted_campus_id: 1, extracted_program_id: 2, extracted_year_level: 1,
  extracted_section: "A", extracted_academic_period: "1st Semester 2025-2026",
  valid_until: null, submitted_at: "2026-09-30T00:00:00Z",
  processed_at: "2026-09-30T00:00:00Z", confirmed_at: null,
};
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const envelope = (items) => ({ items, total: items.length, page: 1, page_size: items.length || 1 });
const failure = (status) => json({ error: { code: "TEST_ERROR", message: "Test error" } }, status);

function environment(t, initialHash = "#home") {
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

function fakeApi(t, recover = () => json(auth), login = auth) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    calls.push({ path: new URL(url, "http://localhost:5173").pathname, ...init });
    if (url.endsWith("/auth/csrf")) return recover();
    if (url.endsWith("/auth/login")) return json(login);
    if (url.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (url.endsWith("/health")) return json({ status: "ok" });
    if (url.endsWith("/cor-screenings/me")) return json(screening);
    if (url.endsWith("/accounts/campuses")) return json(envelope([{ campus_id: 1, campus_name: "Main" }]));
    if (url.endsWith("/accounts/programs")) return json(envelope([{ program_id: 2, program_name: "BS Psychology" }]));
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

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (predicate()) return;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });
  }
  throw new Error("UI did not reach the expected state");
}

test("student login link opens the staff email form and switches back", async (t) => {
  environment(t, "#login");
  fakeApi(t, () => failure(401));
  const root = await mount(t);
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Student number or email");
  const staffLink = root.root.findByProps({ href: "#staff-login" });
  await act(async () => { window.location.hash = staffLink.props.href; });
  assert.equal(root.root.findByType("h1").children.join(""), "Counselor / Staff sign in");
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Email");
  assert.equal(root.root.findByProps({ id: "identifier" }).props.type, "email");
  await act(async () => { window.location.hash = "#login"; });
  assert.equal(root.root.findByProps({ htmlFor: "identifier" }).children.join(""), "Student number or email");
});

test("the reviewer console and its hook no longer exist", async (t) => {
  assert.throws(() => require("../src/pages/ReviewerPage.jsx"), /Cannot find module/);
  assert.throws(() => require("../src/features/enrollment/useReviewerConsole.js"), /Cannot find module/);
  environment(t, "#review");
  const calls = fakeApi(t);
  const root = await mount(t);
  const rendered = JSON.stringify(root.toJSON());
  assert.doesNotMatch(rendered, /Registration review/);
  assert.equal(calls.some((call) => call.path.includes("enrollment-verifications")), false);
  assert.equal(root.root.findAllByProps({ href: "#review" }).length, 0);
});

test("login reaches the home page without a page reload or loss of CSRF", async (t) => {
  environment(t, "#login");
  t.mock.timers.enable({ apis: ["setTimeout"] });
  fakeApi(t, () => failure(401), studentAuth);
  const root = await mount(t);
  await act(async () => {
    root.root.findByProps({ id: "identifier" }).props.onChange({ target: { value: "20231234-A" } });
    root.root.findByProps({ id: "password" }).props.onChange({ target: { value: "synthetic-password" } });
  });
  await act(async () => { await root.root.findByType("form").props.onSubmit({ preventDefault() {} }); });
  await act(async () => { t.mock.timers.tick(700); });
  assert.equal(window.location.hash, "#home");
  assert.equal(window.location.reload.mock.callCount(), 0);
  assert.equal(getCsrfToken(), studentAuth.csrf_token);
});

test("reload waits for CSRF recovery before loading the registration status", async (t) => {
  environment(t, "#registration");
  let resolve;
  const recovery = new Promise((done) => { resolve = done; });
  const calls = fakeApi(t, () => recovery);
  const root = await mount(t);
  assert.match(JSON.stringify(root.toJSON()), /Restoring your session/);
  assert.equal(calls.some((call) => call.path.includes("cor-screenings")), false);
  await act(async () => { resolve(json(studentAuth)); });
  await waitFor(() => calls.some((call) => call.path.endsWith("/cor-screenings/me")));
  assert.match(JSON.stringify(root.toJSON()), /Review your details/);
});

test("failed session recovery never loads confidential screening data", async (t) => {
  environment(t, "#registration");
  const calls = fakeApi(t, () => failure(500));
  const root = await mount(t);
  assert.match(JSON.stringify(root.toJSON()), /Could not restore your session/);
  assert.equal(calls.some((call) => call.path.includes("cor-screenings")), false);
  assert.equal(getCsrfToken(), null);
});

test("sign out uses recovered CSRF and clears the protected screening page", async (t) => {
  environment(t, "#registration");
  const calls = fakeApi(t, () => json(studentAuth));
  const root = await mount(t);
  await waitFor(() => JSON.stringify(root.toJSON()).includes("Review your details"));
  const logout = root.root.findAllByType("button").find((button) => button.children.includes("Sign out"));
  await act(async () => { await logout.props.onClick(); });
  assert.equal(calls.find((call) => call.path.endsWith("/logout")).headers["X-CSRF-Token"], auth.csrf_token);
  assert.equal(getCsrfToken(), null);
  assert.doesNotMatch(JSON.stringify(root.toJSON()), /Review your details/);
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

test("non-envelope error bodies still throw a safe ApiError", async (t) => {
  environment(t);
  // FastAPI default 405: JSON body without the standard error envelope.
  t.mock.method(global, "fetch", async () => json({ detail: "Method Not Allowed" }, 405));
  let caught;
  try {
    await request("/accounts/programs", { method: "PUT", body: "{}" });
  } catch (err) {
    caught = err;
  }
  assert.ok(caught, "405 must reject");
  assert.ok(caught instanceof ApiError, "must be an ApiError");
  assert.equal(caught.status, 405);
  assert.equal(caught.code, "REQUEST_FAILED");
  assert.equal(caught.message, "Method Not Allowed");
  assert.deepEqual(caught.details, {});

  // Standard envelope keeps its exact code and message.
  t.mock.method(global, "fetch", async () => failure(409));
  try {
    await request("/appointments", { method: "POST", body: "{}" });
  } catch (err) {
    caught = err;
  }
  assert.equal(caught.code, "TEST_ERROR");
  assert.equal(caught.message, "Test error");

  // Unparseable body falls back to the generic network error.
  t.mock.method(global, "fetch", async () => new Response("<html>bad gateway</html>", { status: 502 }));
  try {
    await request("/health");
  } catch (err) {
    caught = err;
  }
  assert.equal(caught.code, "NETWORK_ERROR");
  assert.equal(caught.message, "Request failed.");
});
