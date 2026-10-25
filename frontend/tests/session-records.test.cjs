const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const SessionRecordWorkspace = require("../src/components/sessionRecords/SessionRecordWorkspace.jsx").default;

const counselor = { user_id: 1, role_code: "COUNSELOR", first_name: "Cora", last_name: "Test" };
const student = { user_id: 2, role_code: "STUDENT", first_name: "Ana", last_name: "Test" };
const appointment = { appointment_id: 5, status: "CONFIRMED", starts_at: "2099-01-01T01:00:00Z", ends_at: "2099-01-01T02:00:00Z" };

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

function draft(overrides = {}) {
  return {
    appointment_id: 5, record_id: 1, status: "DRAFT",
    notepad: "", presenting_concern: "", session_summary: "", intervention: "", plan: "",
    follow_up_on: null, finalized_at: null, updated_at: "2099-01-01T01:00:00Z",
    can_edit: true, can_finalize: true, can_reopen: false,
    ...overrides,
  };
}

function setup(t, { user, record }) {
  const calls = [];
  global.window = { location: { hash: "#session-record/5" }, addEventListener() {}, removeEventListener() {} };
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    calls.push({ path, method: (init.method ?? "GET").toUpperCase(), body: init.body });
    if (path.endsWith("/documents")) return json([]);
    if (path.endsWith("/record") && (init.method ?? "GET") === "GET") return json(record);
    if (path.endsWith("/record") && init.method === "PUT") {
      const body = JSON.parse(init.body);
      return json(draft({ ...body, record_id: 1 }));
    }
    if (path.endsWith("/record/finalize")) {
      return json(draft({ ...record, status: "FINAL", can_edit: false, can_finalize: false, can_reopen: true, finalized_at: "2099-01-01T02:00:00Z" }));
    }
    throw new Error(`Unexpected request: ${path}`);
  });
  return calls;
}

async function mount(t, user, appt = appointment, variant = "page") {
  let root;
  await act(async () => {
    root = create(React.createElement(SessionRecordWorkspace, { user, appointment: appt, variant }));
  });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

const buttonByText = (root, text) => root.root.findAllByType("button").find(node => {
  const collect = value => typeof value === "string" ? value : Array.isArray(value) ? value.map(collect).join("") : "";
  return collect(node.children).trim() === text;
});

test("counselor autosaves the notepad and finalizes the record", async t => {
  const calls = setup(t, { user: counselor, record: draft() });
  const root = await mount(t, counselor);

  assert.ok(buttonByText(root, "Notes"));
  assert.ok(buttonByText(root, "Record"));
  assert.ok(buttonByText(root, "Files"));

  const notepad = root.root.findAllByType("textarea")[0];
  await act(async () => { notepad.props.onChange({ target: { value: "private draft" } }); });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1600)); });

  const put = calls.find(call => call.method === "PUT" && call.path.endsWith("/record"));
  assert.ok(put, "debounced draft save is sent");
  assert.equal(JSON.parse(put.body).notepad, "private draft");

  await act(async () => { buttonByText(root, "Record").props.onClick(); });
  await act(async () => { buttonByText(root, "Finalize record").props.onClick(); });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

  assert.ok(calls.some(call => call.method === "POST" && call.path.endsWith("/record/finalize")));
  assert.ok(buttonByText(root, "Reopen for editing"), "the finalized record exposes reopen");
  assert.equal(buttonByText(root, "Finalize record"), undefined);
});

test("reopen is available for a finalized completed appointment", async t => {
  setup(t, {
    user: counselor,
    record: draft({
      status: "FINAL", presenting_concern: "Academic stress", session_summary: "Workload pressure",
      intervention: "Coping plan", plan: "Follow up", finalized_at: "2099-01-01T02:00:00Z",
      can_edit: false, can_finalize: false, can_reopen: true,
    }),
  });
  const root = await mount(t, counselor, { ...appointment, status: "COMPLETED" });

  await act(async () => { buttonByText(root, "Record").props.onClick(); });
  assert.ok(buttonByText(root, "Reopen for editing"));
  assert.equal(buttonByText(root, "Finalize record"), undefined);
});

test("student sees only the finalized assessment and files", async t => {
  setup(t, {
    user: student,
    record: draft({
      status: "FINAL", notepad: null, presenting_concern: "Academic stress",
      session_summary: "Workload pressure", intervention: "Coping plan", plan: "Follow up",
      finalized_at: "2099-01-01T02:00:00Z", can_edit: false, can_finalize: false,
    }),
  });
  const root = await mount(t, student, { ...appointment, status: "COMPLETED" });
  const rendered = JSON.stringify(root.toJSON());

  assert.ok(buttonByText(root, "Assessment"));
  assert.ok(buttonByText(root, "Files"));
  assert.equal(buttonByText(root, "Notes"), undefined);
  assert.ok(rendered.includes("Academic stress"));
  assert.ok(rendered.includes("Workload pressure"));
  assert.equal(root.root.findAllByType("textarea").length, 0, "student cannot edit or see the notepad");
});

test("student cannot open the assessment before the appointment is completed", async t => {
  setup(t, { user: student, record: draft({ status: "FINAL", notepad: null, presenting_concern: "Academic stress" }) });
  const root = await mount(t, student);

  assert.equal(buttonByText(root, "Assessment"), undefined);
  assert.ok(buttonByText(root, "Files"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Session files open after the Counselor marks the session completed."));
  assert.equal(root.root.findAllByProps({ type: "file" }).length, 0);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Academic stress"));
});

test("the rail variant leaves session completion to the session page header", async t => {
  setup(t, { user: counselor, record: draft() });
  const root = await mount(t, counselor, appointment, "rail");

  await act(async () => { buttonByText(root, "Record").props.onClick(); });

  assert.equal(buttonByText(root, "Mark as done"), undefined);
  assert.equal(buttonByText(root, "Finalize record"), undefined, "the rail is not the standalone record page");
});
