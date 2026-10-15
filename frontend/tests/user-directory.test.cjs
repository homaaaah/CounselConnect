const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const App = require("../src/App.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient.js");

const counselor = { user_id: 1, email: "counselor@example.edu", role_code: "COUNSELOR",
  account_status: "ACTIVE", first_name: "Cora", last_name: "Reyes" };
const student = { ...counselor, user_id: 2, role_code: "STUDENT",
  email: "ana@example.edu", first_name: "Ana", last_name: "Santos" };
const superadmin = { ...counselor, user_id: 9, role_code: "SUPERADMIN",
  email: "root@example.edu", first_name: "Root", last_name: "Admin" };

const authFor = (user) => ({ user, csrf_token: "synthetic-csrf-token",
  idle_expires_at: "2099-01-01T01:00:00Z", absolute_expires_at: "2099-01-01T12:00:00Z" });

const directoryItem = {
  user: { user_id: 2, email: "ana@example.edu", role_code: "STUDENT",
    account_status: "PENDING_VERIFICATION", first_name: "Ana", middle_name: null, last_name: "Santos" },
  profile: { user_id: 2, student_number: "20231234-A", campus_id: 1, program_id: 1,
    year_level: 1, section: "A" },
  screening: { cor_screening_id: 1, student_user_id: 2, status: "AWAITING_CONFIRMATION",
    format_template_version: "v1", format_match_score: 1.0, extraction_confidence: 1.0,
    barcode_status: "DECODED", barcode_symbology: "Code 39", failure_reason_code: null,
    extracted_student_number: "20231234-A", extracted_first_name: "Ana", extracted_middle_name: null,
    extracted_last_name: "Santos", extracted_campus_id: 1, extracted_program_id: 1,
    extracted_year_level: 1, extracted_section: "A", extracted_academic_period: null,
    valid_until: null, submitted_at: "2026-09-30T00:00:00Z", processed_at: null, confirmed_at: null },
};
const directory = { items: [directoryItem], page: 1, page_size: 20, total: 1 };

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

function environment(t, initialHash = "#users") {
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

function fakeApi(t, auth) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, ...init });
    if (url.endsWith("/auth/csrf")) return json(auth);
    if (url.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (url.endsWith("/health")) return json({ status: "ok" });
    if (path === "/api/v1/accounts/students") return json(directory);
    if (path === "/api/v1/accounts/campuses") return json({ items: [{ campus_id: 1, campus_name: "Main Campus" }] });
    if (path === "/api/v1/accounts/programs") return json({ items: [{ program_id: 1, program_name: "BSIT" }] });
    return json({ items: [] });
  });
  return calls;
}

async function mount(t, component) {
  let root;
  await act(async () => { root = create(component); });
  t.after(async () => { await act(async () => { await root.unmount(); }); });
  return root;
}

test("counselor Users page lists students with their screening status", async (t) => {
  environment(t, "#users");
  const calls = fakeApi(t, authFor(counselor));
  const root = await mount(t, React.createElement(App));
  assert.ok(calls.some((call) => call.path === "/api/v1/accounts/students"), "directory endpoint is called");
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("20231234-A"));
  assert.ok(rendered.includes("Ana"));
  assert.ok(rendered.includes("Santos"));
  assert.ok(rendered.includes("AWAITING CONFIRMATION"));
  assert.ok(rendered.includes("Main Campus"));
  assert.ok(rendered.includes("BSIT"));
});

test("counselor sidebar exposes the Users link", async (t) => {
  environment(t, "#home");
  fakeApi(t, authFor(counselor));
  const root = await mount(t, React.createElement(App));
  assert.ok(root.root.findAllByProps({ href: "#users" }).length >= 1);
});

test("students cannot see or open the Users directory", async (t) => {
  environment(t, "#users");
  fakeApi(t, authFor(student));
  const root = await mount(t, React.createElement(App));
  assert.equal(root.root.findAllByProps({ href: "#users" }).length, 0);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Student accounts and their latest COR screening"));
});

test("counselor can open a student's complete profile and screening", async (t) => {
  environment(t, "#users");
  fakeApi(t, authFor(counselor));
  const root = await mount(t, React.createElement(App));
  const viewButton = root.root.findAllByType("button")
    .find((button) => button.children.join("") === "View");
  assert.ok(viewButton, "directory rows expose a View action");
  await act(async () => { viewButton.props.onClick(); });
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Academic profile"));
  assert.ok(rendered.includes("Latest COR screening"));
  assert.ok(rendered.includes("20231234-A"));
  assert.ok(rendered.includes("Main Campus"));
  assert.ok(rendered.includes("BSIT"));
  // Counselors are read-only: no recovery action.
  assert.equal(
    root.root.findAllByType("button").filter((b) => b.children.join("") === "Recover").length,
    0,
  );
});

test("superadmin can recover a non-active student", async (t) => {
  environment(t, "#users");
  const calls = fakeApi(t, authFor(superadmin));
  const root = await mount(t, React.createElement(App));
  const recover = root.root.findAllByType("button")
    .find((button) => button.children.join("") === "Recover");
  assert.ok(recover, "superadmin sees the Recover action");
  await act(async () => { await recover.props.onClick(); });
  assert.ok(
    calls.some((call) => call.path === "/api/v1/accounts/students/2/recover"),
    "recovery endpoint is called",
  );
});
