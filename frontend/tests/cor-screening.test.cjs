const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const RegistrationStatusPage = require("../src/pages/student/RegistrationStatusPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient.js");

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const envelope = (items) => ({ items, total: items.length, page: 1, page_size: items.length || 1 });

const screening = (overrides = {}) => ({
  cor_screening_id: 7, student_user_id: 2, status: "AWAITING_CONFIRMATION",
  format_template_version: "ucc-registration-v1", format_match_score: 0.9,
  extraction_confidence: 0.9, barcode_status: "DECODED", barcode_symbology: "QR_CODE",
  failure_reason_code: null, extracted_student_number: "20231234-A",
  extracted_first_name: "Ana", extracted_middle_name: null, extracted_last_name: "Santos",
  extracted_campus_id: 1, extracted_program_id: 2, extracted_year_level: 1,
  extracted_section: "A", extracted_academic_period: "1st Semester 2025-2026",
  valid_until: null, submitted_at: "2026-09-30T00:00:00Z",
  processed_at: "2026-09-30T00:00:00Z", confirmed_at: null,
  ...overrides,
});

const CAMPUSES = [{ campus_id: 1, campus_name: "Main" }, { campus_id: 9, campus_name: "North" }];
const PROGRAMS = [{ program_id: 2, program_name: "BS Psychology" }, { program_id: 5, program_name: "BS IT" }];

function setup(t, { me = screening(), confirmResponse, resubmitResponse, rejectResponse } = {}) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/cor-screenings/me")) return json(me);
    if (path.endsWith("/accounts/campuses")) return json(envelope(CAMPUSES));
    if (path.endsWith("/accounts/programs")) return json(envelope(PROGRAMS));
    if (path.endsWith("/cor-screenings/confirm")) {
      return confirmResponse
        ? confirmResponse()
        : json({ screening: screening({ status: "PASSED" }), user: { user_id: 2 }, profile: {} });
    }
    if (path.endsWith("/cor-screenings/reject")) {
      return rejectResponse
        ? rejectResponse()
        : json({ screening: screening({ status: "NEEDS_RESUBMISSION", failure_reason_code: "REJECTED_BY_STUDENT" }) });
    }
    if (path.endsWith("/cor-screenings/resubmit")) {
      return resubmitResponse
        ? resubmitResponse()
        : json({ screening: screening({ status: "AWAITING_CONFIRMATION" }) }, 201);
    }
    return json({ items: [] });
  });
  return calls;
}

async function mount(t, props = {}) {
  let root;
  await act(async () => { root = create(React.createElement(RegistrationStatusPage, props)); });
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
const field = (root, id) => {
  const node = root.root.findAllByProps({ id }).find((candidate) => typeof candidate.type === "string");
  assert.ok(node, `field ${id} renders`);
  return node;
};
const confirmForm = (root) => root.root.findAllByType("form")
  .find((form) => form.findAllByType("button").some((b) => b.children.join("").includes("Confirm details")));
const resubmitForm = (root) => root.root.findAllByType("form")
  .find((form) => form.findAllByProps({ id: "resubmit-cor" }).length > 0);

test("status page seeds the extracted fields and defaults campus/program from the screening", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t);
  const root = await mount(t);
  await waitFor(() => hasId(root, "confirm-student-number"));
  assert.equal(field(root, "confirm-student-number").props.value, "20231234-A");
  // Barcode-backed and verified fields are read-only during verification.
  assert.equal(field(root, "confirm-student-number").props.readOnly, true);
  assert.equal(field(root, "confirm-academic-period").props.readOnly, true);
  assert.equal(field(root, "confirm-academic-period").props.value, "1st Semester 2025-2026");
  assert.equal(field(root, "confirm-first-name").props.value, "Ana");
  assert.equal(field(root, "confirm-last-name").props.value, "Santos");
  assert.equal(field(root, "confirm-first-name").props.readOnly, true);
  assert.equal(field(root, "confirm-section").props.readOnly, true);
  assert.equal(field(root, "confirm-campus").props.value, "Main");
  assert.equal(field(root, "confirm-program").props.value, "BS Psychology");
  assert.equal(field(root, "confirm-year-level").props.value, "1");
  assert.equal(field(root, "confirm-section").props.value, "A");
  assert.equal(root.root.findAllByProps({ id: "resubmit-cor" }).length, 0);
  setCsrfToken(null);
});

test("status page shows campus/program selectors with unmatched hints when extraction missed them", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t, { me: screening({ extracted_campus_id: null, extracted_program_id: null }) });
  const root = await mount(t, { unmatchedCampusName: "UCC Caloocan", unmatchedProgramName: "BS Mystery" });
  await waitFor(() => hasId(root, "confirm-campus"));
  assert.equal(root.root.findByProps({ id: "confirm-campus" }).props.value, "");
  assert.equal(root.root.findByProps({ id: "confirm-program" }).props.value, "");
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("UCC Caloocan"), "unmatched campus name is used as a hint");
  assert.ok(rendered.includes("BS Mystery"), "unmatched program name is used as a hint");
  setCsrfToken(null);
});

test("confirm sends the snake_case academic fields and reports activation", async (t) => {
  setCsrfToken("synthetic-csrf");
  const calls = setup(t);
  const root = await mount(t);
  await waitFor(() => hasId(root, "confirm-section"));
  await act(async () => { await confirmForm(root).props.onSubmit({ preventDefault() {} }); });
  const post = calls.find((call) => call.path.endsWith("/cor-screenings/confirm"));
  assert.equal(post.method, "POST");
  assert.equal(post.headers["X-CSRF-Token"], "synthetic-csrf");
  assert.deepEqual(JSON.parse(post.body), {
    student_number: "20231234-A",
    first_name: "Ana",
    middle_name: null,
    last_name: "Santos",
    campus_id: 1,
    program_id: 2,
    year_level: 1,
    section: "A",
    academic_period: "1st Semester 2025-2026",
  });
  assert.match(JSON.stringify(root.toJSON()), /account is now active/);
  setCsrfToken(null);
});

test("confirm maps SCREENING_NOT_CONFIRMABLE to a friendly message", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t, {
    confirmResponse: () => json({
      error: { code: "SCREENING_NOT_CONFIRMABLE", message: "This screening is not awaiting confirmation." },
    }, 409),
  });
  const root = await mount(t);
  await waitFor(() => hasId(root, "confirm-section"));
  await act(async () => { await confirmForm(root).props.onSubmit({ preventDefault() {} }); });
  assert.match(JSON.stringify(root.toJSON()), /These details can no longer be confirmed/);
  setCsrfToken(null);
});

test("resubmit posts the chosen COR file and explains the screening failure first", async (t) => {
  setCsrfToken("synthetic-csrf");
  const calls = setup(t, { me: screening({ status: "NEEDS_RESUBMISSION", failure_reason_code: "UNREADABLE_DOCUMENT" }) });
  const root = await mount(t);
  await waitFor(() => hasId(root, "resubmit-cor"));
  assert.match(JSON.stringify(root.toJSON()), /No readable text was found in the document/);
  await act(async () => {
    root.root.findByProps({ id: "resubmit-cor" }).props.onChange({
      target: { files: [{ name: "cor.pdf", size: 2048 }] },
    });
  });
  await act(async () => { await resubmitForm(root).props.onSubmit({ preventDefault() {} }); });
  const post = calls.find((call) => call.path.endsWith("/cor-screenings/resubmit"));
  assert.equal(post.method, "POST");
  assert.ok(post.body instanceof FormData);
  assert.ok(post.body.has("file"));
  assert.match(JSON.stringify(root.toJSON()), /registration form was received/i);
  setCsrfToken(null);
});

test("resubmit maps COR_TOO_LARGE to a friendly message", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t, {
    me: screening({ status: "FAILED", failure_reason_code: "TECHNICAL_ERROR" }),
    resubmitResponse: () => json({
      error: { code: "COR_TOO_LARGE", message: "The COR file must be at most 10 MB." },
    }, 422),
  });
  const root = await mount(t);
  await waitFor(() => hasId(root, "resubmit-cor"));
  await act(async () => {
    root.root.findByProps({ id: "resubmit-cor" }).props.onChange({
      target: { files: [{ name: "big.pdf", size: 99 * 1024 * 1024 }] },
    });
  });
  await act(async () => { await resubmitForm(root).props.onSubmit({ preventDefault() {} }); });
  assert.match(JSON.stringify(root.toJSON()), /too large \(max 10 MB\)/i);
  setCsrfToken(null);
});

test("no screening yet offers the COR upload prompt", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t, { me: null });
  const root = await mount(t);
  await waitFor(() => hasId(root, "resubmit-cor"));
  assert.match(JSON.stringify(root.toJSON()), /No registration form \(COR\) was found/);
  assert.equal(root.root.findAllByProps({ id: "confirm-section" }).length, 0);
  setCsrfToken(null);
});

test("reject marks the screening for resubmission and offers re-upload", async (t) => {
  setCsrfToken("synthetic-csrf");
  const calls = setup(t);
  const root = await mount(t);
  await waitFor(() => hasId(root, "confirm-section"));
  const rejectButton = root.root.findAllByType("button")
    .find((button) => button.children.join("").includes("Reject and re-upload"));
  assert.ok(rejectButton, "reject action is offered");
  await act(async () => { await rejectButton.props.onClick(); });
  const post = calls.find((call) => call.path.endsWith("/cor-screenings/reject"));
  assert.ok(post, "reject posts to /cor-screenings/reject");
  assert.equal(post.method, "POST");
  assert.match(JSON.stringify(root.toJSON()), /discarded those details/i);
  await waitFor(() => hasId(root, "resubmit-cor"));
  setCsrfToken(null);
});

test("a successful reject triggers the auto-logout callback", async (t) => {
  setCsrfToken("synthetic-csrf");
  setup(t);
  const onRejected = t.mock.fn();
  const root = await mount(t, { onRejected });
  await waitFor(() => hasId(root, "confirm-section"));
  const rejectButton = root.root.findAllByType("button")
    .find((button) => button.children.join("").includes("Reject and re-upload"));
  await act(async () => { await rejectButton.props.onClick(); });
  assert.equal(onRejected.mock.callCount(), 1);
  setCsrfToken(null);
});
