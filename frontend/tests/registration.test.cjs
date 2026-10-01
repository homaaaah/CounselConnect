const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const RegisterPage = require("../src/pages/RegisterPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient.js");

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

const corFile = (name = "cor.pdf", size = 1024) => ({ name, size });

const screening = (overrides = {}) => ({
  cor_screening_id: 1,
  student_user_id: 2,
  status: "AWAITING_CONFIRMATION",
  failure_reason_code: null,
  ...overrides,
});

async function mount(t, component = React.createElement(RegisterPage)) {
  let root;
  await act(async () => { root = create(component); });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

const field = (root, id) => {
  const node = root.root.findAllByProps({ id }).find((candidate) => typeof candidate.type === "string");
  assert.ok(node, `field ${id} renders`);
  return node;
};

const change = (root, id, value) =>
  act(async () => field(root, id).props.onChange({ target: { value } }));

const attach = (root, id, file) =>
  act(async () => root.root.findByProps({ id }).props.onChange({ target: { files: [file] } }));

const submit = (root) =>
  act(async () => { await root.root.findByType("form").props.onSubmit({ preventDefault() {} }); });

async function fillValid(root) {
  await change(root, "register-email", "ana@example.edu");
  await change(root, "register-password", "password123");
  await change(root, "register-confirm", "password123");
  await attach(root, "register-cor", corFile());
}

test("registration collects only email, password, confirmation, and the COR PDF", async (t) => {
  setCsrfToken(null);
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    calls.push({ url, ...init });
    return json({ items: [] });
  });
  const root = await mount(t);
  const rendered = JSON.stringify(root.toJSON());
  for (const label of ["First name", "Last name", "Middle name", "Student number",
    "Campus", "Program", "Year level", "Section"]) {
    assert.ok(!rendered.includes(label), label + " input must be removed from registration");
  }
  assert.ok(root.root.findByProps({ id: "register-email" }));
  assert.ok(root.root.findByProps({ id: "register-password" }));
  assert.ok(root.root.findByProps({ id: "register-confirm" }));
  assert.ok(root.root.findByProps({ id: "register-cor" }));
  assert.equal(calls.length, 0, "registration no longer loads campus/program reference data");
});

test("registration posts the COR, returns a one-time token, and shows the inline confirm step", async (t) => {
  setCsrfToken(null);
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/accounts/campuses") || path.endsWith("/accounts/programs")) {
      return json({ items: [] });
    }
    return json({
      user: { user_id: 2, email: "ana@example.edu", role_code: "STUDENT" },
      screening: screening(),
      verification_token: "cor-token-1",
      unmatched_campus_name: null,
      unmatched_program_name: null,
      next_step: "CONFIRM_DETAILS",
    }, 201);
  });
  const root = await mount(t);
  await fillValid(root);
  await submit(root);

  const post = calls.find((call) => call.path.endsWith("/accounts/register/student-with-cor"));
  assert.ok(post, "registration submit posts to the screening endpoint");
  assert.equal(post.method, "POST");
  assert.ok(post.body instanceof FormData);
  assert.equal(post.body.get("email"), "ana@example.edu");
  assert.equal(post.body.get("password"), "password123");
  assert.ok(post.body.has("file"), "the COR file is attached");
  assert.ok(
    !calls.some((call) => call.path === "/api/v1/auth/login"),
    "registration must not sign the student in",
  );

  assert.match(JSON.stringify(root.toJSON()), /passed screening/i);
  assert.ok(root.root.findByProps({ id: "confirm-student-number" }), "inline confirmation fields render");
  assert.ok(root.root.findByProps({ id: "confirm-campus" }));
});

test("inline confirmation sends the token, activates the account, and reports success", async (t) => {
  setCsrfToken(null);
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, ...init });
    if (path === "/api/v1/accounts/campuses") return json({ items: [{ campus_id: 1, campus_name: "Main" }] });
    if (path === "/api/v1/accounts/programs") return json({ items: [{ program_id: 1, program_name: "BSIT" }] });
    if (path === "/api/v1/cor-screenings/confirm") {
      return json({ screening: screening({ status: "PASSED" }), user: { user_id: 2 }, profile: {} });
    }
    return json({ user: { user_id: 2 }, screening: screening({
      extracted_student_number: "20231234-A",
      extracted_first_name: "Ana",
      extracted_last_name: "Santos",
      extracted_section: "A",
      extracted_campus_id: 1,
      extracted_program_id: 1,
      extracted_year_level: 1,
      extracted_academic_period: "1st Semester 2025-2026",
    }), verification_token: "cor-token-1", unmatched_campus_name: null, unmatched_program_name: null }, 201);
  });
  const root = await mount(t);
  await fillValid(root);
  await submit(root);

  // Barcode-backed fields are read-only during verification.
  assert.equal(field(root, "confirm-student-number").props.readOnly, true);
  assert.equal(field(root, "confirm-academic-period").props.readOnly, true);
  assert.equal(field(root, "confirm-student-number").props.value, "20231234-A");

  await change(root, "confirm-campus", "1");
  await change(root, "confirm-program", "1");
  await change(root, "confirm-year-level", "1");
  await submit(root);

  const confirm = calls.find((call) => call.path === "/api/v1/cor-screenings/confirm");
  assert.ok(confirm, "the inline confirmation posts to /cor-screenings/confirm");
  assert.equal(confirm.headers["X-COR-Token"], "cor-token-1", "the one-time token authorizes confirm");
  const payload = JSON.parse(confirm.body);
  assert.equal(payload.student_number, "20231234-A");
  assert.equal(payload.campus_id, 1);
  assert.match(JSON.stringify(root.toJSON()), /account activated/i);
  assert.match(JSON.stringify(root.toJSON()), /sign in/i);
  assert.ok(
    !calls.some((call) => call.path === "/api/v1/auth/login"),
    "confirmation does not establish a session",
  );
});

test("registration blocks a password mismatch before calling the API", async (t) => {
  setCsrfToken(null);
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => { calls.push({ url, ...init }); return json({}); });
  const root = await mount(t);
  await change(root, "register-email", "ana@example.edu");
  await change(root, "register-password", "password123");
  await change(root, "register-confirm", "password124");
  await attach(root, "register-cor", corFile());
  await submit(root);
  assert.equal(calls.length, 0);
  assert.match(JSON.stringify(root.toJSON()), /Passwords do not match/);
});

test("registration maps EMAIL_ALREADY_REGISTERED to a friendly message", async (t) => {
  setCsrfToken(null);
  t.mock.method(global, "fetch", async () => json({
    error: { code: "EMAIL_ALREADY_REGISTERED", message: "This email is already registered." },
  }, 409));
  const root = await mount(t);
  await fillValid(root);
  await submit(root);
  assert.match(JSON.stringify(root.toJSON()), /That email is already registered/);
});

test("registration keeps a NEEDS_RESUBMISSION in the same card as an inline re-upload", async (t) => {
  setCsrfToken(null);
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, ...init });
    if (path === "/api/v1/accounts/campuses") return json({ items: [{ campus_id: 1, campus_name: "Main" }] });
    if (path === "/api/v1/accounts/programs") return json({ items: [{ program_id: 1, program_name: "BSIT" }] });
    if (path === "/api/v1/cor-screenings/resubmit") {
      return json({ screening: screening({
        status: "AWAITING_CONFIRMATION",
        extracted_student_number: "20231234-A",
        extracted_first_name: "Ana",
        extracted_last_name: "Santos",
        extracted_section: "A",
        extracted_campus_id: 1,
        extracted_program_id: 1,
        extracted_year_level: 1,
      }), verification_token: "cor-token-2" }, 201);
    }
    return json({
      user: { user_id: 2 },
      screening: screening({ status: "NEEDS_RESUBMISSION", failure_reason_code: "BARCODE_NOT_FOUND" }),
      verification_token: "cor-token-1",
      unmatched_campus_name: null,
      unmatched_program_name: null,
    }, 201);
  });
  const root = await mount(t);
  await fillValid(root);
  await submit(root);

  const rendered = JSON.stringify(root.toJSON());
  assert.match(rendered, /No barcode was found on the document/);
  assert.ok(root.root.findByProps({ id: "resubmit-cor" }), "inline re-upload input is shown in the same card");

  await attach(root, "resubmit-cor", corFile());
  await submit(root);
  const resubmit = calls.find((call) => call.path === "/api/v1/cor-screenings/resubmit");
  assert.ok(resubmit, "re-upload posts inline");
  assert.equal(resubmit.headers["X-COR-Token"], "cor-token-1", "re-upload uses the current token");
  assert.ok(root.root.findByProps({ id: "confirm-student-number" }), "a clean re-upload moves to confirmation");

  // The rotated token from the re-upload authorizes the follow-up confirm.
  await change(root, "confirm-campus", "1");
  await change(root, "confirm-program", "1");
  await change(root, "confirm-year-level", "1");
  await submit(root);
  const confirm = calls.find((call) => call.path === "/api/v1/cor-screenings/confirm");
  assert.ok(confirm, "confirmation after re-upload posts");
  assert.equal(confirm.headers["X-COR-Token"], "cor-token-2", "the rotated token is used");
});
