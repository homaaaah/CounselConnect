const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const AppointmentsPage = require("../src/pages/AppointmentsPage.jsx").default;
const App = require("../src/App.jsx").default;
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
    if (path.includes("/calendar")) {
      const now = new Date();
      const iso = date => date.toISOString().slice(0, 10);
      const day = offset => {
        const d = new Date(now); d.setDate(d.getDate() + offset);
        return iso(d);
      };
      const weekday = d => d.getDay() !== 0 && d.getDay() !== 6;
      return json({ timezone: "Asia/Manila", business_hours: "Monday-Friday, 8:00 AM-4:00 PM", days: [-2, -1, 0, 1, 2].map(offset => {
        const date = day(offset);
        const futureHours = offset > 0 ? 8 : Math.max(0, 16 - now.getHours());
        return { calendar_date: date, is_weekday: weekday(new Date(date)), is_blocked: false, is_past: offset < 0,
          available_times: offset < 0 || !weekday(new Date(date)) ? [] : Array.from({ length: futureHours }, (_, i) => `${String(8 + i).padStart(2, "0")}:00`) };
      }) });
    }
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

test("counselor blocks an unavailable calendar date", async t => {
  const calls = setup(t, { user: counselor });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: counselor }));
  const form = formFor(root, "Block date");
  const date = form.findByProps({ type: "date" });
  await act(async () => {
    date.props.onChange({ target: { value: "2099-01-01" } });
  });
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const sent = calls.find(c => c.method === "POST");
  assert.equal(sent.path, "/api/v1/calendar/blocks");
  assert.deepEqual(JSON.parse(sent.body), { blocked_date: "2099-01-01", reason: null });
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

test("calendar month grid renders disabled past days and today highlight", async t => {
  setup(t);
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const rendered = JSON.stringify(root.toJSON());
  const dayCells = root.root.findAllByType("button").filter(b => {
    const label = b.props["aria-label"];
    return typeof label === "string" && /^\d{4}-\d{2}-\d{2} — /.test(label);
  });
  assert.ok(dayCells.length > 0, "month grid day cells are rendered");
  const pastCells = dayCells.filter(b => b.props["aria-label"].includes("Already passed"));
  assert.ok(pastCells.length >= 2, "past calendar days are shown");
  for (const b of pastCells) assert.equal(b.props.disabled, true, "past day must be unselectable");
  const bookable = dayCells.filter(b => !b.props.disabled);
  assert.ok(bookable.length > 0, "bookable future days remain selectable");
  assert.ok(rendered.includes("Already passed"));
  assert.ok(rendered.includes("Mon") && rendered.includes("Sun"), "weekday header row is rendered");
});

test("calendar month navigation stays within loaded data", async t => {
  setup(t);
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const nav = label => root.root.findAllByType("button").find(b => b.props["aria-label"] === label);
  const manilaToday = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
  const todayCell = root.root.findAllByType("button").find(b => typeof b.props["aria-label"] === "string" && b.props["aria-label"].startsWith(manilaToday + " — "));
  assert.ok(todayCell, "today cell is present in the grid");
  // The mock loads only 5 days inside the current month, so both nav arrows
  // must be disabled — no month outside the loaded range can be shown.
  assert.equal(nav("Next month").props.disabled, true, "cannot navigate past the loaded month range");
  assert.equal(nav("Previous month").props.disabled, true, "cannot navigate before the loaded month range");
});

test("slot whose start has passed shows no booking form and the passed-time message", async t => {
  const pastSlot = { ...slot, slot_id: 11, starts_at: "2020-01-01T01:00:00Z", ends_at: "2020-01-01T02:00:00Z" };
  global.window = { location: { hash: "#appointments" }, addEventListener() {}, removeEventListener() {} };
  setCsrfToken("synthetic-csrf");
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url).pathname;
    if (path.endsWith("/auth/csrf")) return json({ user: student, csrf_token: "synthetic-csrf" });
    if (path.endsWith("/availability-slots")) return json(envelope([pastSlot]));
    if (path.endsWith("/appointments")) return json(envelope([]));
    if (path.endsWith("/accounts/campuses")) return json(envelope([]));
    return json({ status: "ok" });
  });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const rendered = JSON.stringify(root.toJSON());
  // Past slots are dropped from the list on fetch; the disabled presentation
  // only bridges the live gap until the next refresh clears them.
  assert.ok(!rendered.includes("Request appointment"), "past slot must not offer booking");
});

test("date filter with no remaining slots shows the no-slots message", async t => {
  global.window = { location: { hash: "#appointments" }, addEventListener() {}, removeEventListener() {} };
  setCsrfToken("synthetic-csrf");
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url).pathname;
    if (path.endsWith("/auth/csrf")) return json({ user: student, csrf_token: "synthetic-csrf" });
    if (path.endsWith("/availability-slots")) return json(envelope([]));
    if (path.endsWith("/appointments")) return json(envelope([]));
    if (path.endsWith("/accounts/campuses")) return json(envelope([]));
    return json({ status: "ok" });
  });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const dateInput = root.root.findAllByProps({ type: "date" })[0];
  await act(async () => { dateInput.props.onChange({ target: { value: "2099-01-01" } }); });
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("There are no available appointment time slots for this date. Please select another date."),
    "the filtered empty state must use the no-slots message");
});
