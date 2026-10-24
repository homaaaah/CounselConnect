const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const AppointmentsPage = require("../src/pages/AppointmentsPage.jsx").default;
const HomePage = require("../src/pages/HomePage.jsx").default;
const CalendarGrid = require("../src/components/appointments/CalendarGrid.jsx").default;
const BookingModal = require("../src/components/appointments/BookingModal.jsx").default;
const CounselorAppointmentsPage = require("../src/pages/counselor/CounselorAppointmentsPage.jsx").default;
const CounselorSchedulePage = require("../src/pages/counselor/CounselorSchedulePage.jsx").default;
const CounselorHistoryPage = require("../src/pages/counselor/CounselorHistoryPage.jsx").default;
const App = require("../src/App.jsx").default;
const { manilaInputToUTC, formatSchedule } = require("../src/features/appointments");
const { ToastProvider } = require("../src/components/feedback");
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

function setup(t, { user = student, appointments = [], failure = false, calendar, calendarFailure = false, slotsResponse, availabilityBlocks = [] } = {}) {
  const calls = [];
  global.window = { location: { hash: "#appointments" }, addEventListener() {}, removeEventListener() {} };
  setCsrfToken("synthetic-csrf");
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const parsed = new URL(url, "http://localhost:5173");
    const path = parsed.pathname;
    calls.push({ path, query: Object.fromEntries(parsed.searchParams), ...init });
    if (path.endsWith("/auth/csrf")) return json({ user, csrf_token: "synthetic-csrf" });
    if (init.method === "POST") {
      if (failure) return json({ error: { code: "SLOT_UNAVAILABLE", message: "The selected slot is no longer available." } }, 409);
      return json(appointment, 201);
    }
    if (path.endsWith("/accounts/campuses")) return json(envelope([{ campus_id: 1, campus_name: "Main", guidance_office_location: "Room 201" }]));
    if (path.endsWith("/booking-counselors")) return json([{ counselor_user_id: 1, counselor_name: "Cora Test" }]);
    if (path.endsWith("/availability-slots")) {
      const response = slotsResponse ? slotsResponse(parsed.searchParams) : envelope([slot]);
      // The API echoes the requested page size, including selected-date reads.
      return json({ ...response, page_size: Number(parsed.searchParams.get("page_size") || 20) });
    }
    if (path.endsWith("/appointments")) return json(envelope(
      typeof appointments === "function" ? appointments(parsed.searchParams) : appointments
    ));
    if (path.endsWith("/weekly-schedules")) return json([{ weekly_schedule_id: 3, campus_id: 1, day_of_week: 1, start_time: "08:00:00", end_time: "10:00:00", slot_duration_minutes: 30, delivery_mode: "BOTH", is_active: true }]);
    if (path.endsWith("/availability-blocks")) return typeof availabilityBlocks === "function"
      ? availabilityBlocks() : json(availabilityBlocks);
    if (path.includes("/calendar")) {
      if (calendarFailure) return json({ error: { code: "CALENDAR_UNAVAILABLE", message: "Calendar is unavailable." } }, 503);
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
  await act(async () => { root = create(React.createElement(ToastProvider, null, component)); });
  t.after(async () => { await act(async () => root.unmount()); setCsrfToken(null); });
  return root;
}
const buttonText = (b) => {
  const collect = value => typeof value === "string" ? value
    : Array.isArray(value) ? value.map(collect).join("")
      : value && typeof value === "object" ? collect(value.children) : "";
  return collect(b.children).trim();
};
const button = (root, label) => root.root.findAllByType("button").find(b => buttonText(b) === label || buttonText(b).includes(label));
const formFor = (root, label) => root.root.findAllByType("form").find(f => f.findAllByType("button").some(b => buttonText(b).includes(label)));
const chooseCounselor = async root => act(async () => {
  const option = root.root.findAllByType("button").find(item =>
    item.findAllByType("span").some(span => span.children.join("") === "Cora Test"));
  option.props.onClick();
});
const showBookingMonth = async root => act(async () => {
  const month = root.root.findAllByProps({ type: "month" })[0];
  if (month && month.props.value !== "2099-01") month.props.onChange({ target: { value: "2099-01" } });
});
const calendar = () => ({ days: [{ calendar_date: "2099-01-01", is_weekday: true, is_blocked: false, is_past: false, available_times: ["09:00"] }] });

test("student opens the home booking modal, picks a slot, and requests the appointment", async t => {
  const calls = setup(t, { calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  const requestsBefore = calls.length;
  const schedule = button(root, "Start Booking");
  assert.ok(schedule);
  await act(async () => schedule.props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  const dayCell = root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01"));
  await act(async () => dayCell.props.onClick());
  const timeButton = button(root, "9:00 AM");
  await act(async () => timeButton.props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  const form = formFor(root, "Submit request");
  const sent = calls.find(c => c.method === "POST");
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(c => c.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments");
  assert.deepEqual(JSON.parse(post.body), { availability_slot_id: 10, appointment_mode: "ONLINE" });
  assert.equal(post.headers["X-CSRF-Token"], "synthetic-csrf");
  assert.ok(calls.some(call => call.path.endsWith("/calendar") && call.query.counselor_user_id === "1"),
    "calendar availability is scoped to the selected Counselor");
  assert.ok(calls.some(call => call.path.endsWith("/availability-slots") && call.query.counselor_user_id === "1"),
    "slot search is scoped to the selected Counselor");
  assert.ok(JSON.stringify(root.toJSON()).includes("Awaiting counselor review."));
  // Scheduling data is fetched only when the modal opens.
  assert.ok(calls.slice(requestsBefore).some(c => c.path.endsWith("/calendar")), "calendar loads when the modal opens");
});

test("booking modal shows the revealed campus/time details before requesting", async t => {
  setup(t, { calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Start Booking").props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Review your appointment"));
  assert.ok(rendered.includes("Main"), "campus is included in review");
  assert.ok(rendered.includes("Cora Test"), "counselor is revealed");
  assert.ok(rendered.includes("9:00 AM"), "slot time is revealed");
});

test("session mode choices match the selected slot's supported delivery mode", async t => {
  setup(t, { calendar: calendar(), slotsResponse: () => envelope([{ ...slot, delivery_mode: "ONLINE" }]) });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Start Booking").props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(item => item.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  const options = root.root.findByType("select").findAllByType("option").map(option => option.props.value);
  assert.deepEqual(options, ["ONLINE"]);
});

test("booking loads every selected-date slot page and lets the student choose a matching counselor", async t => {
  const matchingSlots = Array.from({ length: 101 }, (_, index) => ({
    ...slot,
    slot_id: index + 10,
    counselor_name: `Counselor ${index + 1}`,
    campus_name: `Campus ${index + 1}`,
  }));
  const calls = setup(t, {
    calendar: calendar(),
    slotsResponse: (query) => {
      const page = Number(query.get("page") || "1");
      const pageSize = Number(query.get("page_size") || "20");
      if (!query.has("starts_after")) return envelope([slot]);
      const items = matchingSlots.slice((page - 1) * pageSize, page * pageSize);
      return { items, total: matchingSlots.length, page, page_size: pageSize };
    },
  });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Start Booking").props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  assert.ok(calls.some(call => call.path.endsWith("/availability-slots") && call.query.page === "2" && call.query.page_size === "100"));
  const option = root.root.findAllByType("button").find(b => b.props["aria-label"] === "Choose Campus 101 at Counselor 101");
  assert.ok(option, "the second API page is offered as a booking choice");
  await act(async () => option.props.onClick());
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  await act(async () => formFor(root, "Submit request").props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(call => call.method === "POST").at(-1);
  assert.deepEqual(JSON.parse(post.body), { availability_slot_id: 110, appointment_mode: "ONLINE" });
});

test("a background slot refresh preserves a selected compatible appointment mode", async t => {
  global.window = { addEventListener() {}, removeEventListener() {} };
  const modalState = (slots) => ({
    bookingCounselors: [{ counselor_user_id: 1, counselor_name: "Cora Test" }], bookingCounselorsError: "",
    counselorUserId: "", setCounselorUserId() {}, bookingCounselorsLoading: false,
    calendar: calendar(), date: "", setDate() {}, slotPage: 1, setSlotPage() {},
    loading: false, slots: { items: slots, total: slots.length, page: 1, page_size: 20 },
    busy: false, error: "", mutate: async () => true,
  });
  let root;
  await act(async () => { root = create(React.createElement(BookingModal, { open: true, state: modalState([slot]) })); });
  t.after(async () => { await act(async () => root.unmount()); });
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findByType(CalendarGrid).props.onPickTime("2099-01-01", "09:00"));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  let mode = root.root.findByType("select");
  await act(async () => mode.props.onChange({ target: { value: "FACE_TO_FACE" } }));
  assert.equal(root.root.findByType("select").props.value, "FACE_TO_FACE");
  await act(async () => root.update(React.createElement(BookingModal, { open: true, state: modalState([{ ...slot }]) })));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  assert.equal(root.root.findByType("select").props.value, "FACE_TO_FACE");
  await act(async () => button(root, "Review appointment").props.onClick());
  await act(async () => button(root, "Back").props.onClick());
  assert.equal(root.root.findByType("select").props.value, "FACE_TO_FACE", "back navigation retains the compatible mode");
  await act(async () => root.update(React.createElement(BookingModal, { open: true, state: modalState([]) })));
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  assert.ok(JSON.stringify(root.toJSON()).includes("This selected slot is no longer available."),
    "a refreshed slot that disappeared is reported without silently switching campuses");
});

test("server booking conflict keeps the modal open and shows the slot-unavailable error", async t => {
  setup(t, { failure: true, calendar: calendar() });
  const root = await mount(t, React.createElement(HomePage, { user: student }));
  await act(async () => button(root, "Start Booking").props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  await act(async () => formFor(root, "Submit request").props.onSubmit({ preventDefault() {} }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("The selected slot is no longer available."));
  assert.ok(rendered.includes("Submit request"), "form stays available for another try");
});

test("confirmed student record opens the reschedule modal and sends reschedule", async t => {
  const calls = setup(t, { appointments: [appointment], calendar: calendar() });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const requestsBefore = calls.length;
  await act(async () => button(root, "Reschedule").props.onClick());
  await chooseCounselor(root);
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  await act(async () => formFor(root, "Submit reschedule").props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(c => c.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments/5/reschedule");
  assert.ok(JSON.stringify(root.toJSON()).includes("Rescheduled. Awaiting counselor review."));
});

test("Counselor reschedule starts on their own calendar and never needs the student directory", async t => {
  const calls = setup(t, { user: counselor, appointments: [appointment], calendar: calendar() });
  const root = await mount(t, React.createElement(CounselorHistoryPage, { user: counselor }));
  await act(async () => button(root, "Reschedule").props.onClick());
  const opened = JSON.stringify(root.toJSON());
  assert.ok(opened.includes("Step 2 of 6: Date"), "Counselor starts at the calendar step");
  assert.ok(!opened.includes("No active Counselors are available right now."));
  await showBookingMonth(root);
  await act(async () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01")).props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  await act(async () => button(root, "Continue").props.onClick());
  await act(async () => button(root, "Review appointment").props.onClick());
  await act(async () => formFor(root, "Submit reschedule").props.onSubmit({ preventDefault() {} }));
  const post = calls.filter(c => c.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments/5/reschedule");
  assert.ok(JSON.stringify(root.toJSON()).includes("Rescheduled. Awaiting counselor review."));
});

test("records view keeps every appointment outcome accessible by status", async t => {
  setup(t, { appointments: [appointment] });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("My Appointments"), "records heading for students");
  const labels = ["Confirmed", "Pending", "Completed", "No-show", "Cancelled", "Rejected"];
  const tabs = root.root.findAllByType("button").filter(b => labels.includes(buttonText(b)));
  assert.equal(tabs.length, labels.length, "every appointment status has a record tab");
  const confirmed = tabs.find(b => buttonText(b) === "Confirmed");
  assert.equal(confirmed.props["aria-selected"], true, "confirmed is the default tab");
  for (const tab of tabs.filter(b => b !== confirmed)) assert.equal(tab.props["aria-selected"], false);
  assert.ok(!rendered.includes("Find an available slot"), "slot list is gone from the records page");
});

test("student can open rejected history and read the Counselor note", async t => {
  const rejected = { ...appointment, status: "REJECTED", rejection_note: "Please choose another available time." };
  const calls = setup(t, {
    appointments: query => query.get("status") === "REJECTED" ? [rejected] : [appointment],
  });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  await act(async () => {
    button(root, "Rejected").props.onClick();
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  assert.ok(calls.some(call => call.path.endsWith("/appointments") && call.query.status === "REJECTED"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Please choose another available time."));
});

test("Counselor can open cancelled appointment history", async t => {
  const cancelled = { ...appointment, status: "CANCELLED" };
  const calls = setup(t, {
    user: counselor,
    appointments: query => query.get("status") === "CANCELLED" ? [cancelled] : [appointment],
  });
  const root = await mount(t, React.createElement(CounselorHistoryPage, { user: counselor }));
  await act(async () => root.root.findByProps({ "aria-label": "Filter session history, Confirmed" }).props.onClick());
  await act(async () => {
    button(root, "Cancelled").props.onClick();
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  assert.ok(calls.some(call => call.path.endsWith("/appointments") && call.query.status === "CANCELLED"));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("CANCELLED"));
  assert.ok(rendered.includes("Ana Test"));
});

test("counselor history search filters records by student name", async t => {
  const other = { ...appointment, appointment_id: 6, student_name: "Bea Cruz" };
  setup(t, { user: counselor, appointments: [appointment, other] });
  const root = await mount(t, React.createElement(CounselorHistoryPage, { user: counselor }));
  const search = root.root.findAllByType("input").find(input => input.props.placeholder === "Search");
  assert.ok(search, "history exposes a search field");
  await act(async () => search.props.onChange({ target: { value: "bea" } }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Bea Cruz"));
  assert.ok(!rendered.includes("Ana Test"), "non-matching rows are filtered out");
});

test("calendar failure does not prevent appointment records from loading", async t => {
  const calls = setup(t, { appointments: [appointment], calendarFailure: true });
  const root = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  assert.ok(calls.some(call => call.path.endsWith("/appointments")), "records request still runs");
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Cora Test"), "successful records remain visible");
  assert.ok(rendered.includes("Could not load the availability calendar."));
});

test("availability-block failure on the Schedule page can recover", async t => {
  let attempts = 0;
  const block = { availability_block_id: 7, counselor_user_id: 1, starts_at: "2099-01-01T01:00:00Z", ends_at: "2099-01-01T02:00:00Z", is_all_day: false, reason: "Training" };
  const calls = setup(t, {
    user: counselor,
    appointments: [appointment],
    availabilityBlocks: () => attempts++ === 0
      ? json({ error: { code: "BLOCKS_UNAVAILABLE", message: "Unavailable times are temporarily unavailable." } }, 503)
      : json([block]),
  });
  const root = await mount(t, React.createElement(CounselorSchedulePage, { user: counselor }));
  let rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Unavailable times are temporarily unavailable."));
  await act(async () => {
    button(root, "Retry unavailable times").props.onClick();
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Training"), "the recovered block list is displayed");
  assert.equal(calls.filter(call => call.path.endsWith("/availability-blocks")).length, 2);
});

test("counselor blocks an unavailable calendar date", async t => {
  const calls = setup(t, { user: counselor });
  const root = await mount(t, React.createElement(CounselorSchedulePage, { user: counselor }));
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
  const root = await mount(t, React.createElement(CounselorSchedulePage, { user: counselor }));
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
  // Replacement is one atomic API action; the client never leaves two active
  // definitions if a second request fails.
  const posts = calls.filter(c => c.method === "POST");
  const schedulePost = posts.find(c => c.path.endsWith("/weekly-schedules/3/replace"));
  assert.deepEqual(JSON.parse(schedulePost.body), {
    campus_id: 1, day_of_week: 2, start_time: "08:00:00", end_time: "11:00:00",
    slot_duration_minutes: 30, delivery_mode: "BOTH",
  });
  assert.equal(calls.some(c => c.method === "DELETE" && c.path.endsWith("/weekly-schedules/3")), false);
});

test("counselor accepts a pending request from the Appointment Requests page", async t => {
  const pending = { ...appointment, status: "PENDING" };
  const calls = setup(t, { user: counselor, appointments: [pending] });
  const root = await mount(t, React.createElement(CounselorAppointmentsPage, { user: counselor }));
  assert.ok(calls.some(call => call.path.endsWith("/appointments") && call.query.status === "PENDING"),
    "the requests queue loads pending appointments only");
  const accept = button(root, "Accept Appointment");
  assert.ok(accept, "a pending request exposes Accept Appointment");
  await act(async () => accept.props.onClick());
  const post = calls.filter(call => call.method === "POST").at(-1);
  assert.equal(post.path, "/api/v1/appointments/5/confirm");
});

test("counselor pages split requests, availability, and history", async t => {
  setup(t, { user: counselor, appointments: [appointment] });
  const requests = await mount(t, React.createElement(CounselorAppointmentsPage, { user: counselor }));
  const requestsBody = JSON.stringify(requests.toJSON());
  assert.ok(requestsBody.includes("Appointment Requests"), "requests heading");
  assert.ok(!requestsBody.includes("Your weekly availability"), "availability is not on the requests page");
  assert.ok(!requestsBody.includes("Student records"), "records are not on the requests page");

  const schedule = await mount(t, React.createElement(CounselorSchedulePage, { user: counselor }));
  assert.ok(JSON.stringify(schedule.toJSON()).includes("Your weekly availability"), "availability edit mode lives on Schedule");

  const history = await mount(t, React.createElement(CounselorHistoryPage, { user: counselor }));
  assert.ok(JSON.stringify(history.toJSON()).includes("Student records"), "records live on History");

  const studentPage = await mount(t, React.createElement(AppointmentsPage, { user: student }));
  const studentBody = JSON.stringify(studentPage.toJSON());
  assert.ok(studentBody.includes("My Appointments"), "student heading unchanged");
  assert.ok(!studentBody.includes("Appointment Requests"), "student page must not show the counselor review queue");
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

test("calendar permits a weekend date when it has counselor availability", async t => {
  setup(t);
  const picks = [];
  const cal = { business_hours: "Availability set by counselors", days: [{
    calendar_date: "2099-01-03", is_weekday: false, is_blocked: false, is_past: false,
    available_times: ["09:00"],
  }] };
  const root = await mount(t, React.createElement(CalendarGrid, {
    calendar: cal, onPickTime: (...args) => picks.push(args),
  }));
  const saturday = root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-03"));
  assert.equal(saturday.props.disabled, false);
  assert.match(saturday.props["aria-label"], /1 times available/);
  await act(async () => saturday.props.onClick());
  await act(async () => button(root, "9:00 AM").props.onClick());
  assert.deepEqual(picks, [["2099-01-03", "09:00"]]);
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
    let now = Date.parse("2099-01-01T05:30:00Z"); // 1:30 PM Manila
    t.mock.method(Date, "now", () => now);
    const timers = [];
    t.mock.method(global, "setInterval", (callback, delay) => { timers.push({ callback, delay }); return 1; });
    t.mock.method(global, "clearInterval", () => {});
    const cal = { days: [{ calendar_date: "2099-01-01",
      is_weekday: true, is_blocked: false, is_past: false,
      available_times: ["08:00", "13:30", "14:00", "14:30"] }] };
    const root = await mount(t, React.createElement(CalendarGrid, { calendar: cal }));
    const cell = () => root.root.findAllByType("button").find(b => b.props["aria-label"]?.startsWith("2099-01-01"));
    assert.match(cell().props["aria-label"], /2 times available/);
    await act(async () => cell().props.onClick());
    assert.ok(button(root, "2:00 PM"));
    now = Date.parse("2099-01-01T06:00:00Z");
    await act(async () => timers.find(timer => timer.delay === 1000).callback());
    assert.match(cell().props["aria-label"], /1 times available/);
    assert.equal(button(root, "2:00 PM"), undefined);
    assert.ok(button(root, "2:30 PM"));
    now = Date.parse("2099-01-01T06:30:00Z");
    await act(async () => timers.find(timer => timer.delay === 1000).callback());
    assert.match(cell().props["aria-label"], /No available time slots/);
    assert.ok(JSON.stringify(root.toJSON()).includes("There are no available appointment time slots"));
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
