const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-typescript.cjs");
const AppointmentsPage = require("../src/pages/AppointmentsPage.tsx").default;
const App = require("../src/App.tsx").default;
const { manilaInputToUTC, formatSchedule } = require("../src/features/appointments");
const { setCsrfToken } = require("../src/services/apiClient");

const student = { user_id: 2, role_code: "STUDENT", account_status: "ACTIVE", first_name: "Ana", last_name: "Test", email: "synthetic@example.edu" };
const counselor = { ...student, user_id: 1, role_code: "COUNSELOR" };
const slot = { slot_id: 10, counselor_user_id: 1, counselor_name: "Cora Test", campus_id: 1, campus_name: "Main",
  guidance_office_location: "Room 201", delivery_mode: "BOTH", status: "AVAILABLE",
  starts_at: "2099-01-01T01:00:00Z", ends_at: "2099-01-01T02:00:00Z" };
const appointment = { appointment_id: 5, student_user_id: 2, student_name: "Ana Test", counselor_user_id: 1,
  counselor_name: "Cora Test", campus_id: 1, campus_name: "Main", availability_slot_id: 9, appointment_mode: "ONLINE",
  starts_at: slot.starts_at, ends_at: slot.ends_at, status: "CONFIRMED", conversation_id: null, meeting_location: null, rejection_note: null };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const envelope = items => ({ items, total: items.length, page: 1, page_size: 20 });

function setup(t, { user = student, appointments = [], failure = false } = {}) {
  const calls = [];
  global.window = { location: { hash: "#appointments" }, addEventListener() {}, removeEventListener() {} };
  setCsrfToken("synthetic-csrf");
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/auth/csrf")) return json({ user, csrf_token: "synthetic-csrf" });
    if (init.method === "POST") {
      if (failure) return json({ error: { code: "SLOT_UNAVAILABLE", message: "The selected slot is no longer available." } }, 409);
      return json(appointment, 201);
    }
    if (path.endsWith("/accounts/campuses")) return json(envelope([{ campus_id: 1, campus_name: "Main", guidance_office_location: "Room 201" }]));
    if (path.endsWith("/availability-slots")) return json(envelope([slot]));
    if (path.endsWith("/appointments")) return json(envelope(appointments));
    return json({ status: "ok" });
  });
  return calls;
}
async function mount(t, component) {
  let root;
  await act(async () => { root = create(component); });
  t.after(async () => { await act(async () => root.unmount()); setCsrfToken(null); });
  return root;
}
const button = (root, label) => root.root.findAllByType("button").find(b => b.children.includes(label));
const formFor = (root, label) => root.root.findAllByType("form").find(f => f.findAllByType("button").some(b => b.children.includes(label)));

test("student submits selected mode and displays server booking conflicts", async t => {
  const calls = setup(t, { failure: true });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const form = formFor(root, "Request appointment");
  await act(async () => form.findByType("select").props.onChange({ target: { value: "FACE_TO_FACE" } }));
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const sent = calls.find(c => c.method === "POST");
  assert.deepEqual(JSON.parse(sent.body), { availability_slot_id: 10, appointment_mode: "FACE_TO_FACE" });
  assert.equal(sent.headers["X-CSRF-Token"], "synthetic-csrf");
  assert.ok(JSON.stringify(root.toJSON()).includes("The selected slot is no longer available."));
});

test("confirmed student appointment selects a replacement and sends reschedule", async t => {
  const calls = setup(t, { appointments: [appointment] });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  await act(async () => button(root, "Reschedule").props.onClick());
  await act(async () => formFor(root, "Choose replacement").props.onSubmit({ preventDefault() {} }));
  assert.ok(calls.some(c => c.path === "/api/v1/appointments/5/reschedule" && c.method === "POST"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Rescheduled. Awaiting counselor review."));
});

test("counselor creates concrete slots with Philippine input converted to UTC", async t => {
  const calls = setup(t, { user: counselor });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: counselor }));
  // The availability campus selector precedes search filters.
  await act(async () => root.root.findAllByType("select")[0].props.onChange({ target: { value: "1" } }));
  const form = formFor(root, "Create slots");
  const dates = form.findAllByProps({ type: "datetime-local" });
  await act(async () => {
    dates[0].props.onChange({ target: { value: "2099-01-01T09:00" } });
    dates[1].props.onChange({ target: { value: "2099-01-01T10:00" } });
    form.findByProps({ type: "number" }).props.onChange({ target: { value: "30" } });
  });
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const sent = calls.find(c => c.method === "POST");
  assert.equal(sent.path, "/api/v1/availability-slots");
  assert.deepEqual(JSON.parse(sent.body), { campus_id: 1, delivery_mode: "ONLINE",
    starts_at: "2099-01-01T01:00:00.000Z", ends_at: "2099-01-01T02:00:00.000Z", slot_duration_minutes: 30 });
  assert.equal(button(root, "Request appointment"), undefined);
});

for (const [role, status] of [["GUIDANCE_STAFF", "ACTIVE"], ["STUDENT", "PENDING_VERIFICATION"], ["STUDENT", "VERIFICATION_EXPIRED"]]) {
  test(role + " " + status + " cannot mount appointments or fetch private scheduling data", async t => {
    const calls = setup(t, { user: { ...student, role_code: role, account_status: status } });
    const root = await mount(t, React.createElement(App));
    assert.ok(JSON.stringify(root.toJSON()).includes("Appointments require an active"));
    assert.equal(calls.filter(c => c.path.endsWith("/appointments") || c.path.endsWith("/availability-slots")).length, 0);
  });
}

test("Philippine schedule formatting is independent of browser timezone", () => {
  assert.equal(manilaInputToUTC("2099-01-01T09:00"), "2099-01-01T01:00:00.000Z");
  assert.match(formatSchedule("2099-01-01T01:00:00Z"), /9:00/);
});
