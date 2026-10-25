const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const CounselorDashboard = require("../src/pages/counselor/counselor_dashboard.jsx").default;
const { manilaToday } = require("../src/features/appointments");
const { setCsrfToken } = require("../src/services/apiClient");

const counselor = {
  user_id: 1, email: "counselor@example.edu", role_code: "COUNSELOR",
  account_status: "ACTIVE", first_name: "Cora", last_name: "Reyes",
};

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});
const envelope = (items, total = items.length) => ({ items, total, page: 1, page_size: items.length || 1 });

const addDays = (day, days) => {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, date + days)).toISOString().slice(0, 10);
};
const mondayOf = (day) => {
  const [year, month, date] = day.split("-").map(Number);
  const weekday = new Date(Date.UTC(year, month - 1, date)).getUTCDay(); // 0 = Sunday
  return addDays(day, -((weekday + 6) % 7));
};
const spanDays = (params) =>
  Math.round((Date.parse(params.ends_before) - Date.parse(params.starts_after)) / 86400000);

const appointmentAt = (id, day, hour, status = "CONFIRMED") => ({
  appointment_id: id,
  student_user_id: 100 + id,
  student_name: `Student ${id}`,
  counselor_user_id: 1,
  counselor_name: "Cora Reyes",
  campus_id: 1,
  campus_name: "Main",
  availability_slot_id: 500 + id,
  appointment_mode: "ONLINE",
  starts_at: new Date(`${day}T${String(hour).padStart(2, "0")}:00:00+08:00`).toISOString(),
  ends_at: new Date(`${day}T${String(hour).padStart(2, "0")}:30:00+08:00`).toISOString(),
  status,
  conversation_id: null,
  meeting_location: null,
  rejection_note: null,
});

function setup(t, { today = [], week = [], todayStatus = 200, weekStatus = 200 } = {}) {
  const calls = [];
  setCsrfToken("synthetic-csrf-token");
  t.mock.method(global, "fetch", async (url) => {
    const parsed = new URL(url, "http://localhost:5173");
    const params = Object.fromEntries(parsed.searchParams);
    calls.push({ path: parsed.pathname, params });
    if (parsed.pathname.endsWith("/accounts/students")) return json(envelope([], 9));
    if (!parsed.pathname.endsWith("/appointments")) return json({ status: "ok" });
    // KPI cards call /appointments without a range.
    if (!params.starts_after) return json(envelope([]));
    const daily = spanDays(params) <= 1;
    const source = daily ? today : week;
    const status = daily ? todayStatus : weekStatus;
    if (status !== 200) {
      return json({ error: { code: "TEST_ERROR", message: daily ? "Today failed" : "Week failed" } }, status);
    }
    const page = Number(params.page ?? 1);
    const size = Number(params.page_size ?? 20);
    return json({
      items: source.slice((page - 1) * size, page * size),
      total: source.length, page, page_size: size,
    });
  });
  t.after(() => { setCsrfToken(null); });
  return calls;
}

async function mount(t) {
  let root;
  await act(async () => { root = create(React.createElement(CounselorDashboard, { user: counselor })); });
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

const rendered = (root) => JSON.stringify(root.toJSON());
const section = (root, heading) => root.root.findAllByType("section").find((node) =>
  node.findAllByType("h2").some((title) => title.children.join("") === heading));

test("today's list caps at five rows while the summary keeps the full day", async (t) => {
  const today = manilaToday();
  setup(t, { today: Array.from({ length: 7 }, (_, i) => appointmentAt(i + 1, today, 8 + i)) });
  const root = await mount(t);
  await waitFor(() => section(root, "Today's appointments")?.findAllByType("li").length === 5);

  const rows = section(root, "Today's appointments").findAllByType("li");
  assert.equal(rows.length, 5);
  assert.match(rendered(root), /7 appointments today/, "the banner still reports the whole day");
  assert.match(rendered(root), /Showing 5 of 7/);
  const footer = section(root, "Today's appointments").findAllByProps({ href: "#history" })
    .find((node) => node.children.join("") === "View all appointments");
  assert.ok(footer, "the hidden rows are reachable from the footer");
  assert.equal(rows[0].findAllByType("p")[0].children.join(""), "Student 1", "the earliest rows stay first");
});

test("five or fewer appointments render without a truncation footer", async (t) => {
  const today = manilaToday();
  setup(t, { today: Array.from({ length: 5 }, (_, i) => appointmentAt(i + 1, today, 8 + i)) });
  const root = await mount(t);
  await waitFor(() => section(root, "Today's appointments")?.findAllByType("li").length === 5);
  assert.doesNotMatch(rendered(root), /Showing 5 of 5/);
});

test("weekly volume counts the current Manila week and skips cancelled/rejected", async (t) => {
  const monday = mondayOf(manilaToday());
  setup(t, {
    week: [
      appointmentAt(1, monday, 9),
      appointmentAt(2, monday, 10),
      appointmentAt(3, addDays(monday, 2), 9),
      appointmentAt(4, addDays(monday, 1), 9, "CANCELLED"),
      appointmentAt(5, addDays(monday, 1), 10, "REJECTED"),
    ],
  });
  const root = await mount(t);
  await waitFor(() => rendered(root).includes("Mon: 2"));

  const body = rendered(root);
  assert.doesNotMatch(body, /No weekly appointment volume yet/);
  assert.ok(root.root.findAllByProps({ "aria-label": "Weekly appointment volume" }).length > 0);
  assert.match(body, /Mon: 2/);
  assert.match(body, /Tue: 0/, "cancelled and rejected appointments are not volume");
  assert.match(body, /Wed: 1/);
  assert.match(body, /Sun: 0/);
});

test("weekly volume requests the Mon-Sun range and reads every page", async (t) => {
  const monday = mondayOf(manilaToday());
  const week = Array.from({ length: 101 }, (_, i) => appointmentAt(i + 1, addDays(monday, i % 7), 8));
  const calls = setup(t, { week });
  await mount(t);
  await waitFor(() => calls.some((call) => call.params.starts_after
    && call.params.page === "2" && spanDays(call.params) === 7));

  const firstPage = calls.find((call) => call.params.starts_after
    && call.params.page === "1" && spanDays(call.params) === 7);
  assert.ok(firstPage, "a seven-day range is requested");
  assert.equal(firstPage.params.page_size, "100");
  assert.equal(firstPage.params.starts_after, new Date(`${monday}T00:00:00+08:00`).toISOString());
  assert.equal(firstPage.params.ends_before,
    new Date(new Date(`${monday}T00:00:00+08:00`).getTime() + 7 * 86400000).toISOString());
  // Independently of the helper: the window starts on a Manila Monday and contains now.
  assert.equal(new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Manila", weekday: "short" })
    .format(new Date(firstPage.params.starts_after)), "Mon");
  assert.ok(Date.parse(firstPage.params.starts_after) <= Date.now());
  assert.ok(Date.parse(firstPage.params.ends_before) > Date.now());
});

test("case distribution sits beside today's list and availability beside the chart", async (t) => {
  setup(t, {});
  const root = await mount(t);
  await waitFor(() => rendered(root).includes("Weekly appointment volume"));

  const rows = root.root.findAllByType("div")
    .filter((node) => node.props.className === "grid gap-6 lg:grid-cols-3");
  assert.equal(rows.length, 3, "banner row, today row, chart row");

  const headings = (node) => node.findAllByType("h2")
    .map((title) => title.children.join("")).sort();

  assert.deepEqual(headings(rows[1]), ["Case distribution", "Today's appointments"].sort());
  assert.deepEqual(headings(rows[2]), ["Availability update", "Weekly appointment volume"].sort());
});

test("a failed week read is an error, not an empty week", async (t) => {
  const today = manilaToday();
  setup(t, { today: [appointmentAt(1, today, 9)], weekStatus: 500 });
  const root = await mount(t);
  await waitFor(() => root.root.findAllByProps({ role: "alert" })
    .some((node) => node.children.join("").includes("Week failed")));

  const body = rendered(root);
  assert.doesNotMatch(body, /No weekly appointment volume yet/);
  assert.match(body, /Student 1/, "today's list still renders");
});

test("a failed today read still renders the weekly chart", async (t) => {
  const monday = mondayOf(manilaToday());
  setup(t, { week: [appointmentAt(1, monday, 9)], todayStatus: 500 });
  const root = await mount(t);
  await waitFor(() => rendered(root).includes("Mon: 1"));

  const body = rendered(root);
  assert.match(body, /Today failed/);
  assert.doesNotMatch(body, /No weekly appointment volume yet/);
});
