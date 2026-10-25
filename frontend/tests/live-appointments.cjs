// Real component forms and API requests. Python provides a disposable loopback server.
// Drives the redesigned scheduling UI: the counselor availability editor,
// the student home booking modal (calendar -> time -> mode), and the
// counselor records tabs (pending review -> confirm -> cancel).
const assert = require("node:assert/strict");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const CounselorAppointmentsPage = require("../src/pages/counselor/CounselorAppointmentsPage.jsx").default;
const CounselorSchedulePage = require("../src/pages/counselor/CounselorSchedulePage.jsx").default;
const CounselorHistoryPage = require("../src/pages/counselor/CounselorHistoryPage.jsx").default;
const HomePage = require("../src/pages/HomePage.jsx").default;
const { request, setCsrfToken } = require("../src/services/apiClient");
const { ToastProvider } = require("../src/components/feedback");
const base = process.env.COUNSELCONNECT_TEST_API_URL;
assert.ok(base && new URL(base).hostname === "127.0.0.1", "A disposable loopback API is required");
const nativeFetch = global.fetch;
let cookie = "", root;
// CalendarGrid/BookingModal register window listeners (focus, keydown), so
// the mock window must support add/removeEventListener.
const events = new EventTarget();
global.window = {
  location: { hash: "#appointments" },
  addEventListener: events.addEventListener.bind(events),
  removeEventListener: events.removeEventListener.bind(events),
};
global.fetch = async (url, init = {}) => {
  assert.equal(new URL(url).origin, new URL(base).origin);
  const headers = new Headers(init.headers);
  if (cookie) headers.set("Cookie", cookie);
  const response = await nativeFetch(url, { ...init, headers });
  if (response.headers.get("set-cookie")) cookie = response.headers.get("set-cookie").split(";", 1)[0];
  return response;
};

async function waitFor(check) {
  for (let i = 0; i < 500; i++) {
    if (check()) return;
    await act(async () => new Promise(resolve => setTimeout(resolve, 20)));
  }
  throw new Error("Expected scheduling UI state was not reached: " + JSON.stringify(root?.toJSON()));
}
const buttonText = (b) => {
  const collect = value => typeof value === "string" ? value
    : Array.isArray(value) ? value.map(collect).join("")
      : value && typeof value === "object" ? collect(value.children) : "";
  return collect(b.children).trim();
};
const allButtons = () => root.root.findAllByType("button");
const button = (label) => allButtons()
  .find(b => buttonText(b) === label || buttonText(b).includes(label));
const exactButton = (label) => allButtons().find(b => buttonText(b) === label);
const formFor = (label) => root.root.findAllByType("form")
  .find(f => f.findAllByType("button").some(b => buttonText(b).includes(label)));
const dayCell = () => allButtons().find(b =>
  typeof b.props["aria-label"] === "string" && /^\d{4}-\d{2}-\d{2} — /.test(b.props["aria-label"]));

async function signIn(identifier, Component, ready) {
  if (root) { await act(async () => root.unmount()); root = null; }
  setCsrfToken(null);
  const auth = await request("/auth/login", { method: "POST", body: JSON.stringify({ identifier, password: "synthetic-live-pass" }) });
  setCsrfToken(auth.csrf_token);
  await act(async () => { root = create(React.createElement(ToastProvider, null, React.createElement(Component, { user: auth.user }))); });
  await waitFor(ready);
  return auth;
}

/** First calendar day offering bookable times, navigating months if needed. */
async function pickBookableDay() {
  await waitFor(() => Boolean(dayCell()));
  const bookable = () => allButtons().find(b =>
    typeof b.props["aria-label"] === "string" && /\d{4}-\d{2}-\d{2} — \d+ times available$/.test(b.props["aria-label"]));
  for (let attempt = 0; attempt < 2 && !bookable(); attempt++) {
    const next = allButtons().find(b => b.props["aria-label"] === "Next month");
    assert.ok(next && !next.props.disabled, "no bookable day in the loaded calendar range");
    await act(async () => next.props.onClick());
  }
  const cell = bookable();
  assert.ok(cell, "no calendar day shows available times");
  await act(async () => cell.props.onClick());
}

async function main() {
  try {
    // Counselor saves a recurring weekly schedule through the real editor (Schedule page).
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL, CounselorSchedulePage,
      () => Boolean(formFor("Add availability")));
    await waitFor(() => Boolean(formFor("Add availability")));
    await act(async () => {
      const selects = formFor("Add availability").findAllByType("select");
      selects[0].props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_CAMPUS_ID } });
      selects[2].props.onChange({ target: { value: "BOTH" } });
      const times = formFor("Add availability").findAllByProps({ type: "time" });
      times[0].props.onChange({ target: { value: "08:00" } });
      times[1].props.onChange({ target: { value: "10:00" } });
    });
    await act(async () => formFor("Add availability").props.onSubmit({ preventDefault() {} }));
    await waitFor(() => JSON.stringify(root.toJSON()).includes("Weekly schedule saved."));

    // The student books a materialized slot face-to-face through the home modal.
    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT_NUMBER, HomePage,
      () => Boolean(button("Start Booking")));
    await act(async () => button("Start Booking").props.onClick());
    await waitFor(() => allButtons().some(b =>
      b.findAllByType("span").some(span => span.children.join("") === "Cora Live")));
    await act(async () => allButtons()
      .find(b => b.findAllByType("span").some(span => span.children.join("") === "Cora Live"))
      .props.onClick());
    await pickBookableDay();
    const timeButton = async () => {
      for (let i = 0; i < 250; i++) {
        const time = allButtons().find(b => /^\d{1,2}:\d{2}\s?(AM|PM)\b/.test(buttonText(b)));
        if (time) return time;
        await act(async () => new Promise(resolve => setTimeout(resolve, 20)));
      }
      throw new Error("No time buttons rendered for the selected day");
    };
    await act(async () => (await timeButton()).props.onClick());
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
    await waitFor(() => Boolean(button("Continue")));
    await act(async () => button("Continue").props.onClick());
    await waitFor(() => Boolean(root.root.findAllByType("select").length));
    await act(async () => root.root.findByType("select")
      .props.onChange({ target: { value: "FACE_TO_FACE" } }));
    await act(async () => button("Review appointment").props.onClick());
    await waitFor(() => Boolean(formFor("Submit request")));
    await act(async () => formFor("Submit request").props.onSubmit({ preventDefault() {} }));
    await waitFor(() => JSON.stringify(root.toJSON()).includes("Awaiting counselor review."));

    // Counselor reviews the pending request on the Appointment Requests page...
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL, CounselorAppointmentsPage,
      () => Boolean(exactButton("Accept Appointment")));
    await act(async () => exactButton("Accept Appointment").props.onClick());
    // The pending queue empties once the confirmation and refresh finish.
    // Gating on the button disappearing proves the confirm-mutate's finally
    // released the mutating guard; clicking through a still-busy state would
    // silently drop the later cancel (direct onClick bypasses disabled).
    await waitFor(() => !exactButton("Accept Appointment") && !exactButton("Reject"));

    // ...then cancels the confirmed record from the History page; the
    // released slot becomes available again.
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL, CounselorHistoryPage,
      () => Boolean(exactButton("Reschedule")));
    await act(async () => exactButton("Cancel appointment").props.onClick());
    await waitFor(() => Boolean(exactButton("Confirm cancellation")));
    await act(async () => exactButton("Confirm cancellation").props.onClick());
    await waitFor(() => !exactButton("Cancel appointment") && !exactButton("Reschedule"));

    // Verify the released reservation through the real API client.
    const cancelled = await request("/appointments?status=CANCELLED");
    assert.equal(cancelled.total, 1, "exactly one cancelled appointment expected");
    assert.equal(cancelled.items[0].meeting_location, "Synthetic Office 201", "face-to-face location snapshot missing");
    console.log("Live scheduling flow passed: weekly schedule, materialized slots, book, confirm, cancel.");
  } finally {
    if (root) await act(async () => root.unmount());
  }
}
main().catch(err => { console.error(err.stack || err.message); process.exitCode = 1; });
