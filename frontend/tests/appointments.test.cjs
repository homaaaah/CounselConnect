const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const AppointmentsPage = require("../src/pages/AppointmentsPage.jsx").default;
const HomePage = require("../src/pages/HomePage.jsx").default;
const CalendarGrid = require("../src/components/appointments/CalendarGrid.jsx").default;
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

function setup(t, { user = student, appointments = [], failure = false, calendar } = {}) {
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
    if (path.endsWith("/weekly-schedules")) return json([{ weekly_schedule_id: 3, campus_id: 1, day_of_week: 1, start_time: "08:00:00", end_time: "10:00:00", slot_duration_minutes: 30, delivery_mode: "BOTH", is_active: true }]);
    if (path.endsWith("/availability-blocks")) return json([]);
    if (path.includes("/calendar")) {
      if (calendar) return json(calendar);
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
const buttonText = (b) => b.children.filter(c => typeof c === "string").join("").trim();
const button = (root, label) => root.root.findAllByType("button").find(b => buttonText(b) === label || buttonText(b).includes(label));
const formFor = (root, label) => root.root.findAllByType("form").find(f => f.findAllByType("button").some(b => buttonText(b).includes(label)));
const calendar = () => ({ days: [{ calendar_date: "2099-01-01", is_weekday: true, is_blocked: false, is_past: false, available_times: ["09:00"] }] });

test("student opens the home booking modal, picks a slot, and requests the appointment", async t => {
  const calls = setup(t, { calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  const requestsBefore = calls.length;
  const schedule = button(root, "Schedule");
  assert.ok(schedule);
  await act(async () => schedule.props.onClick());
  const dayCell = root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01"));
  await act(async () => dayCell.props.onClick());
  const timeButton = button(root, "09:00");
  await act(async () => timeButton.props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  const form = formFor(root, "Confirm booking");
  const sent = calls.find(c => c.method === "POST");
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(c => c.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments");
  assert.deepEqual(JSON.parse(post.body), { availability_slot_id: 10, appointment_mode: "ONLINE" });
  assert.equal(post.headers["X-CSRF-Token"], "synthetic-csrf");
  assert.ok(JSON.stringify(root.toJSON()).includes("Request submitted. Awaiting counselor review."));
  // Scheduling data is fetched only when the modal opens.
  assert.ok(calls.slice(requestsBefore).some(c => c.path.endsWith("/calendar")), "calendar loads when the modal opens");
});

test("booking modal shows the revealed campus/time details before requesting", async t => {
  setup(t, { calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Schedule").props.onClick());
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "09:00").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Additional information"));
  assert.ok(rendered.includes("Main"), "campus is revealed");
  assert.ok(rendered.includes("Cora Test"), "counselor is revealed");
  assert.ok(rendered.includes("9:00 AM"), "slot time is revealed");
});

test("server booking conflict keeps the modal open and shows the slot-unavailable error", async t => {
  setup(t, { failure: true, calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Schedule").props.onClick());
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "09:00").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => formFor(root, "Confirm booking").props.onSubmit({ preventDefault() {} }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("The selected slot is no longer available."));
  assert.ok(rendered.includes("Confirm booking"), "form stays available for another try");
});

test("confirmed student record opens the reschedule modal and sends reschedule", async t => {
  const calls = setup(t, { appointments: [appointment], calendar: calendar() });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const requestsBefore = calls.length;
  await act(async () => button(root, "Reschedule").props.onClick());
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "09:00").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => formFor(root, "Confirm reschedule").props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(c => c.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments/5/reschedule");
  assert.ok(JSON.stringify(root.toJSON()).includes("Rescheduled. Awaiting counselor review."));
});

test("records view defaults to the confirmed tab and can switch statuses", async t => {
  setup(t, { appointments: [appointment] });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("My appointments"), "records heading for students");
  const tabs = root.root.findAllByType("button").filter(b => ["Confirmed", "Pending", "Completed"].includes(buttonText(b)));
  assert.equal(tabs.length, 3, "three record status tabs");
  const confirmed = tabs.find(b => buttonText(b) === "Confirmed");
  assert.equal(confirmed.props["aria-selected"], true, "confirmed is the default tab");
  for (const tab of tabs.filter(b => b !== confirmed)) assert.equal(tab.props["aria-selected"], false);
  assert.ok(!rendered.includes("Find an available slot"), "slot list is gone from the records page");
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
});

test("counselor edit mode seeds the form and replaces a weekly schedule", async t => {
  const calls = setup(t, { user: counselor });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: counselor }));
  // The seeded availability row shows the documented fields.
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Your weekly availability"));
  // Row fields render as separate text nodes; check each part.
  assert.ok(rendered.includes("Monday"));
  assert.ok(rendered.includes("-minute slots"));
  assert.ok(rendered.includes("Online or face-to-face"));
  // Edit seeds the form with the existing definition's values.
  await act(async () => button(root, "Edit").props.onClick());
  const selects = root.root.findAllByType("select");
  assert.equal(selects[0].props.value, "1", "campus is seeded");
  assert.equal(selects[1].props.value, "1", "Monday is seeded");
  // Change the day to Tuesday and the end time, then save.
  await act(async () => selects[1].props.onChange({ target: { value: "2" } }));
  const endTime = root.root.findAllByProps({ type: "time" })[1];
  await act(async () => endTime.props.onChange({ target: { value: "11:00" } }));
  await act(async () => formFor(root, "Save changes").props.onSubmit({ preventDefault() {} }));
  // Replace flow: POST the corrected definition, then DELETE the old one.
  const posts = calls.filter(c => c.method === "POST");
  const schedulePost = posts.find(c => c.path.endsWith("/weekly-schedules"));
  assert.deepEqual(JSON.parse(schedulePost.body), {
    campus_id: 1, day_of_week: 2, start_time: "08:00:00", end_time: "11:00:00",
    slot_duration_minutes: 30, delivery_mode: "BOTH",
  });
  const del = calls.find(c => c.method === "DELETE" && c.path.endsWith("/weekly-schedules/3"));
  assert.ok(del, "the replaced definition is deactivated");
});

test("counselor page shows student records and availability sections distinctly from the student page", async t => {
  setup(t, { user: counselor, appointments: [appointment] });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: counselor }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Student appointments"), "counselor heading");
  assert.ok(rendered.includes("Student records"), "counselor records section");
  assert.ok(rendered.includes("Your weekly availability"), "counselor edit mode");
  assert.ok(!rendered.includes("My appointments"), "student heading must not appear for counselor");
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
  const root = await mount(t, React.createElement(CalendarGrid, { calendar: calendarWithDays() }));
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
  const root = await mount(t, React.createElement(CalendarGrid, { calendar: calendarWithDays() }));
  const nav = label => root.root.findAllByType("button").find(b => b.props["aria-label"] === label);
  const manilaToday = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila" }).format(new Date());
  const todayCell = root.root.findAllByType("button").find(b => typeof b.props["aria-label"] === "string" && b.props["aria-label"].startsWith(manilaToday + " — "));
  assert.ok(todayCell, "today cell is present in the grid");
  // The mock loads only 5 days inside the current month, so both nav arrows
  // must be disabled — no month outside the loaded range can be shown.
  assert.equal(nav("Next month").props.disabled, true, "cannot navigate past the loaded month range");
  assert.equal(nav("Previous month").props.disabled, true, "cannot navigate before the loaded month range");
});

for (const user of [student, counselor]) {
  test(user.role_code + " calendar count and selected times expire without a network refresh", async t => {
    let now = Date.parse("2026-09-11T05:30:00Z"); // 1:30 PM Manila
    t.mock.method(Date, "now", () => now);
    const timers = [];
    t.mock.method(global, "setInterval", (callback, delay) => { timers.push({ callback, delay }); return 1; });
    t.mock.method(global, "clearInterval", () => {});
    const cal = { days: [{ calendar_date: "2026-09-11",
      is_weekday: true, is_blocked: false, is_past: false,
      available_times: ["08:00", "13:30", "14:00", "14:30"] }] };
    const root = await mount(t, React.createElement(CalendarGrid, { calendar: cal }));
    const cell = () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2026-09-11"));
    assert.match(cell().props["aria-label"], /2 times available/);
    await act(async () => cell().props.onClick());
    assert.ok(button(root, "14:00"));
    now = Date.parse("2026-09-11T06:00:00Z");
    await act(async () => timers.find(timer => timer.delay === 1000).callback());
    assert.match(cell().props["aria-label"], /1 times available/);
    assert.equal(button(root, "14:00"), undefined);
    assert.ok(button(root, "14:30"));
    now = Date.parse("2026-09-11T06:30:00Z");
    await act(async () => timers.find(timer => timer.delay === 1000).callback());
    assert.match(cell().props["aria-label"], /No available time slots/);
    assert.ok(JSON.stringify(root.toJSON()).includes("No times left"));
  });
}

/** Calendar mock with a 5-day window around today for grid tests. */
function calendarWithDays() {
  const now = new Date();
  const iso = date => date.toISOString().slice(0, 10);
  const day = offset => {
    const d = new Date(now); d.setDate(d.getDate() + offset);
    return iso(d);
  };
  const weekday = d => d.getDay() !== 0 && d.getDay() !== 6;
  return { timezone: "Asia/Manila", business_hours: "Monday-Friday, 8:00 AM-4:00 PM",
    days: [-2, -1, 0, 1, 2].map(offset => {
      const date = day(offset);
      const futureHours = offset > 0 ? 8 : Math.max(0, 16 - now.getHours());
      return { calendar_date: date, is_weekday: weekday(new Date(date)), is_blocked: false, is_past: offset < 0,
        available_times: offset < 0 || !weekday(new Date(date)) ? [] : Array.from({ length: futureHours }, (_, i) => `${String(8 + i).padStart(2, "0")}:00`) };
    }) };
}
