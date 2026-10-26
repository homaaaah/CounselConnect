const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");

const ScheduledSessionPage = require("../src/pages/ScheduledSessionPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient");

const user = { user_id: 2, role_code: "STUDENT", account_status: "ACTIVE" };
const counselorUser = { user_id: 1, role_code: "COUNSELOR", account_status: "ACTIVE" };
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});
const textContent = node => {
  const collect = value => typeof value === "string" ? value : Array.isArray(value) ? value.map(collect).join("") : "";
  return collect(node.children).trim();
};
const buttonByText = (root, text) => root.root.findAllByType("button").find(node => textContent(node) === text);
const buttonsByText = (root, text) => root.root.findAllByType("button").filter(node => textContent(node) === text);
// Let the load -> auto-join -> catch-up chain and its follow-up renders settle.
const settle = async () => {
  await act(async () => {
    for (let index = 0; index < 5; index += 1) {
      await new Promise(resolve => setTimeout(resolve, 0));
    }
  });
};

function studentSession({ now, joined }) {
  return {
    appointment_id: 7,
    conversation_id: joined ? 11 : null,
    appointment_mode: "ONLINE",
    status: "CONFIRMED",
    starts_at: new Date(now - 60_000).toISOString(),
    ends_at: new Date(now + 3_600_000).toISOString(),
    lobby_opens_at: new Date(now - 1_800_000).toISOString(),
    messaging_opens_at: new Date(now - 60_000).toISOString(),
    safety_deadline_at: new Date(now + 4_500_000).toISOString(),
    server_time: new Date(now).toISOString(),
    student_joined_at: joined ? new Date(now).toISOString() : null,
    counselor_joined_at: null,
    conversation_status: joined ? "OPEN" : null,
    closure_reason: null,
    capabilities: {
      can_open_lobby: true,
      can_join: true,
      can_send: joined,
      can_read_history: joined,
      can_call: false,
      can_cancel: false,
      can_reschedule: false,
      can_change_mode: false,
    },
  };
}

function testWindow() {
  global.window = {
    location: { origin: "http://localhost:5173", hash: "#session/7" },
    addEventListener() {},
    removeEventListener() {},
  };
}

test("scheduled session joins automatically, catches up, and persists a message", async t => {
  const now = Date.now();
  let joined = false;
  const calls = [];
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json(studentSession({ now, joined }));
    }
    if (path.endsWith("/appointments/7/session/join")) {
      joined = true;
      return json({ conversation_id: 11 });
    }
    if (path.endsWith("/conversations/11/messages") && init.method === "POST") {
      const body = JSON.parse(init.body);
      return json({
        message_id: 21,
        conversation_id: 11,
        sender_user_id: 2,
        client_message_id: body.client_message_id,
        sequence_number: 1,
        body: body.body,
        sent_at: new Date(now).toISOString(),
      });
    }
    if (path.endsWith("/conversations/11/messages")) {
      return json({ items: [], next_before_sequence: null, next_after_sequence: 0, has_more: false, sequence_watermark: 0 });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, { user, appointmentId: 7 }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();

  assert.ok(
    calls.some(call => call.path.endsWith("/appointments/7/session/join") && call.method === "POST"),
    "the open page submits the join request without a click"
  );
  const joinCalls = calls.filter(call => call.path.endsWith("/appointments/7/session/join"));
  assert.equal(joinCalls.length, 1, "the join is submitted exactly once");
  assert.equal(
    joinCalls[0].headers["X-Background-Refresh"], "1",
    "the automatic join does not renew idle activity"
  );
  assert.equal(buttonByText(root, "Join scheduled session"), undefined, "the manual join button is gone");
  assert.ok(
    !calls.some(call => call.path.endsWith("/appointments/7/record")),
    "the Student page never requests the Counselor record"
  );

  const textarea = root.root.findByType("textarea");
  await act(async () => textarea.props.onChange({ target: { value: "Hello counselor" } }));
  const form = root.root.findByType("form");
  await act(async () => form.props.onSubmit({ preventDefault() {} }));
  await settle();

  const sent = calls.find(call => call.path.endsWith("/conversations/11/messages") && call.method === "POST");
  assert.equal(JSON.parse(sent.body).body, "Hello counselor");
  const messages = root.root.findByProps({ "aria-label": "Session messages" });
  const renderedMessages = messages.findAllByType("li").map(textContent).join(" ");
  assert.ok(renderedMessages.includes("Hello counselor"), "the sent message renders in the list");
  assert.equal(root.root.findByType("textarea").props.value, "", "a successful send clears the composer");
});

test("counselor joins a conversation the student opened first without clicking", async t => {
  const now = Date.now();
  let counselorJoined = false;
  const calls = [];
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json({
        appointment_id: 7, conversation_id: 11, appointment_mode: "ONLINE", status: "CONFIRMED",
        starts_at: new Date(now - 60_000).toISOString(), ends_at: new Date(now + 3_600_000).toISOString(),
        lobby_opens_at: new Date(now - 1_800_000).toISOString(), messaging_opens_at: new Date(now - 60_000).toISOString(),
        safety_deadline_at: new Date(now + 4_500_000).toISOString(), server_time: new Date(now).toISOString(),
        student_joined_at: new Date(now - 30_000).toISOString(), counselor_joined_at: counselorJoined ? new Date(now).toISOString() : null,
        conversation_status: "OPEN", closure_reason: null,
        capabilities: { can_open_lobby: true, can_join: !counselorJoined, can_send: counselorJoined, can_read_history: counselorJoined, can_call: false, can_cancel: false, can_reschedule: false, can_change_mode: false },
      });
    }
    if (path.endsWith("/appointments/7/session/join")) {
      counselorJoined = true;
      return json({ conversation_id: 11 });
    }
    if (path.endsWith("/appointments/7/record")) {
      return json({
        appointment_id: 7, record_id: 1, status: "DRAFT", notepad: "",
        presenting_concern: "", session_summary: "", intervention: "", plan: "",
        follow_up_on: null, finalized_at: null, updated_at: new Date(now).toISOString(),
        can_edit: true, can_finalize: true, can_reopen: false,
      });
    }
    if (path.endsWith("/conversations/11/messages")) {
      return json({ items: [], next_before_sequence: null, next_after_sequence: 0, has_more: false, sequence_watermark: 0 });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, {
      user: { user_id: 1, role_code: "COUNSELOR", account_status: "ACTIVE" }, appointmentId: 7,
    }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();

  assert.equal(counselorJoined, true);
  assert.ok(
    calls.some(call => call.path.endsWith("/appointments/7/session/join") && call.method === "POST"),
    "the counselor auto-joins the existing conversation"
  );
});

test("a failed automatic join shows an error and retries manually", async t => {
  const now = Date.now();
  let joined = false;
  let joinAttempts = 0;
  const calls = [];
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json(studentSession({ now, joined }));
    }
    if (path.endsWith("/appointments/7/session/join")) {
      joinAttempts += 1;
      if (joinAttempts === 1) {
        return json({ error: { code: "SESSION_JOIN_FAILED", message: "Could not join the session." } }, 503);
      }
      joined = true;
      return json({ conversation_id: 11 });
    }
    if (path.endsWith("/conversations/11/messages")) {
      return json({ items: [], next_before_sequence: null, next_after_sequence: 0, has_more: false, sequence_watermark: 0 });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, { user, appointmentId: 7 }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();

  assert.equal(joinAttempts, 1, "the failed attempt is not retried on every tick");
  const autoJoin = calls.find(call => call.path.endsWith("/appointments/7/session/join"));
  assert.equal(autoJoin.headers["X-Background-Refresh"], "1", "the automatic attempt is a background request");
  assert.ok(buttonByText(root, "Retry joining"), "the failure exposes a retry control");
  const alerts = root.root.findAllByProps({ role: "alert" }).map(textContent).join(" ");
  assert.ok(alerts.includes("Could not join the session."));

  await act(async () => { await buttonByText(root, "Retry joining").props.onClick(); });
  await settle();

  assert.equal(joinAttempts, 2);
  const retryJoin = calls.filter(call => call.path.endsWith("/appointments/7/session/join"))[1];
  assert.equal(retryJoin.headers["X-Background-Refresh"], undefined, "the manual retry is a normal user action");
  assert.equal(joined, true);
  assert.equal(buttonByText(root, "Retry joining"), undefined);
  assert.ok(root.root.findByType("textarea"), "the manual retry opens the composer");
});

test("a lobby open before start joins on the first tick after messaging opens", async t => {
  const now = Date.now();
  const startMs = now + 300;
  let joined = false;
  const calls = [];
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      const live = Date.now() >= startMs;
      return json({
        appointment_id: 7, conversation_id: joined ? 11 : null, appointment_mode: "ONLINE", status: "CONFIRMED",
        starts_at: new Date(startMs).toISOString(), ends_at: new Date(startMs + 3_600_000).toISOString(),
        lobby_opens_at: new Date(now - 1_800_000).toISOString(), messaging_opens_at: new Date(startMs).toISOString(),
        safety_deadline_at: new Date(startMs + 4_500_000).toISOString(), server_time: new Date(now).toISOString(),
        student_joined_at: joined ? new Date(now).toISOString() : null, counselor_joined_at: null,
        conversation_status: joined ? "OPEN" : null, closure_reason: null,
        capabilities: { can_open_lobby: true, can_join: live, can_send: joined, can_read_history: joined, can_call: false, can_cancel: false, can_reschedule: false, can_change_mode: false },
      });
    }
    if (path.endsWith("/appointments/7/session/join")) {
      joined = true;
      return json({ conversation_id: 11 });
    }
    if (path.endsWith("/conversations/11/messages")) {
      return json({ items: [], next_before_sequence: null, next_after_sequence: 0, has_more: false, sequence_watermark: 0 });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, { user, appointmentId: 7 }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();

  assert.ok(JSON.stringify(root.toJSON()).includes("Session lobby"), "the lobby is shown before start");
  assert.equal(calls.some(call => call.path.endsWith("/session/join")), false, "no join before the window opens");

  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1100)); });
  await settle();

  assert.ok(
    calls.some(call => call.path.endsWith("/appointments/7/session") && call.headers?.["X-Background-Refresh"] === "1"),
    "the boundary refreshes the cached lobby capabilities"
  );
  const joinCalls = calls.filter(call => call.path.endsWith("/appointments/7/session/join"));
  assert.equal(joinCalls.length, 1, "the refreshed post-start state joins once");
  assert.equal(joined, true);
});

test("scheduled session shows the appointment call panel without requesting media", async t => {
  const now = Date.now();
  const mediaCalls = [];
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    writable: true,
    value: { mediaDevices: { getUserMedia: async constraints => { mediaCalls.push(constraints); } } },
  });
  t.after(() => {
    if (navigatorDescriptor) Object.defineProperty(globalThis, "navigator", navigatorDescriptor);
    else delete globalThis.navigator;
  });
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async url => {
    const path = new URL(url, window.location.origin).pathname;
    if (path.endsWith("/appointments/7/session")) {
      return json({
        appointment_id: 7, conversation_id: null, appointment_mode: "ONLINE", status: "CONFIRMED",
        starts_at: new Date(now - 60_000).toISOString(), ends_at: new Date(now + 3_600_000).toISOString(),
        lobby_opens_at: new Date(now - 1_800_000).toISOString(), messaging_opens_at: new Date(now - 60_000).toISOString(),
        safety_deadline_at: new Date(now + 4_500_000).toISOString(), server_time: new Date(now).toISOString(),
        student_joined_at: null, counselor_joined_at: null, conversation_status: null, closure_reason: null,
        capabilities: { can_open_lobby: true, can_join: false, can_send: false, can_read_history: false, can_call: true, can_cancel: false, can_reschedule: false, can_change_mode: false },
      });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, { user, appointmentId: 7 }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();

  const joinCall = root.root.findAllByType("button").find(button =>
    button.children.includes("Join video call")
  );
  assert.ok(joinCall, "the call panel offers an explicit join action");
  assert.equal(mediaCalls.length, 0, "mounting the session must not open the camera");
});

function markDoneHarness(t, { onMarkDone, initialRecord = "DRAFT", recordFailure = false } = {}) {
  const now = Date.now();
  const values = {
    notepad: "", presenting_concern: "Academic stress",
    session_summary: "Workload pressure.", intervention: "Coping plan.", plan: "Follow up in two weeks.",
  };
  let sessionStatus = "CONFIRMED";
  let recordStatus = initialRecord;
  const calls = [];
  const sessionBody = () => ({
    appointment_id: 7, conversation_id: null, appointment_mode: "ONLINE", status: sessionStatus,
    starts_at: new Date(now - 60_000).toISOString(), ends_at: new Date(now + 3_600_000).toISOString(),
    lobby_opens_at: new Date(now - 1_800_000).toISOString(), messaging_opens_at: new Date(now - 60_000).toISOString(),
    safety_deadline_at: new Date(now + 4_500_000).toISOString(), server_time: new Date(now).toISOString(),
    student_joined_at: null, counselor_joined_at: null, conversation_status: null, closure_reason: null,
    capabilities: {
      can_open_lobby: true, can_join: false, can_send: false, can_read_history: false,
      can_call: false, can_cancel: false, can_reschedule: false, can_change_mode: false,
    },
  });
  const recordBody = () => ({
    appointment_id: 7, record_id: 1, status: recordStatus, ...values, follow_up_on: null,
    finalized_at: recordStatus === "FINAL" ? new Date(now).toISOString() : null,
    updated_at: new Date(now).toISOString(),
    can_edit: recordStatus === "DRAFT", can_finalize: recordStatus === "DRAFT", can_reopen: recordStatus === "FINAL",
  });
  testWindow();
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, method: (init.method ?? "GET").toUpperCase(), body: init.body });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json(sessionBody());
    }
    if (path.endsWith("/appointments/7") && (!init.method || init.method === "GET")) {
      return json({
        appointment_id: 7, student_name: "Ana Test", counselor_name: "Cora Test",
        campus_name: "Main", appointment_mode: "ONLINE", status: sessionStatus,
        concern_categories: ["ACADEMIC_PROBLEM", "FAMILY_PROBLEM"],
        concern_details: "School stress",
      });
    }
    if (path.endsWith("/appointments/7/record") && (!init.method || init.method === "GET")) {
      if (recordFailure) {
        return json({ error: { code: "RECORD_UNAVAILABLE", message: "The session record could not be loaded." } }, 503);
      }
      return json(recordBody());
    }
    if (path.endsWith("/appointments/7/record") && init.method === "PUT") {
      const body = JSON.parse(init.body);
      for (const key of Object.keys(values)) values[key] = body[key] ?? "";
      return json(recordBody());
    }
    if (path.endsWith("/appointments/7/mark-done") && init.method === "POST") {
      if (onMarkDone) return onMarkDone();
      recordStatus = "FINAL";
      sessionStatus = "COMPLETED";
      return json(sessionBody());
    }
    if (path.endsWith("/appointments/7/documents")) return json([]);
    throw new Error(`Unexpected request: ${path}`);
  });
  return { calls, session: () => sessionStatus, record: () => recordStatus };
}

test("session Details shows student appointment concerns separately from the counselor record", async t => {
  const harness = markDoneHarness(t);
  const root = await mountCounselor(t);
  await act(async () => buttonByText(root, "Details").props.onClick());
  await settle();

  const content = JSON.stringify(root.toJSON());
  assert.match(content, /Student-stated concern/);
  assert.match(content, /Academic problem/);
  assert.match(content, /Priority/);
  assert.match(content, /School stress/);
  assert.doesNotMatch(content, /presenting concern/i);
  assert.ok(harness.calls.some(call => call.path.endsWith("/appointments/7")));
});

async function mountCounselor(t) {
  let root;
  await act(async () => {
    root = create(React.createElement(ScheduledSessionPage, { user: counselorUser, appointmentId: 7 }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  await settle();
  return root;
}

async function openRecordTab(root) {
  await act(async () => buttonByText(root, "Session record").props.onClick());
  await act(async () => buttonByText(root, "Record").props.onClick());
}

test("counselor marks the session done from the header beside no-show", async t => {
  const harness = markDoneHarness(t);
  const root = await mountCounselor(t);

  assert.ok(buttonByText(root, "Mark as done"), "the completion action is in the header");
  assert.ok(buttonByText(root, "Mark no-show"), "no-show remains in the header");
  assert.equal(buttonByText(root, "Mark completed"), undefined, "History-only completion stays off this page");
  const headerButtons = root.root.findAllByType("button").map(textContent);
  assert.ok(
    headerButtons.indexOf("Mark as done") < headerButtons.indexOf("Mark no-show"),
    "Mark as done precedes Mark no-show"
  );

  await openRecordTab(root);
  assert.equal(buttonsByText(root, "Mark as done").length, 1, "the Record panel no longer duplicates the action");
  assert.equal(buttonByText(root, "Finalize record"), undefined, "the rail keeps no Finalize button");

  const plan = root.root.findAllByType("textarea").at(-1);
  await act(async () => plan.props.onChange({ target: { value: "Revised follow-up plan." } }));
  await act(async () => { await buttonByText(root, "Mark as done").props.onClick(); });
  await settle();

  const put = harness.calls.find(call => call.method === "PUT" && call.path.endsWith("/record"));
  const done = harness.calls.find(call => call.method === "POST" && call.path.endsWith("/mark-done"));
  assert.ok(put && done, "the record saves before the completion request");
  assert.ok(harness.calls.indexOf(put) < harness.calls.indexOf(done));
  assert.equal(JSON.parse(put.body).plan, "Revised follow-up plan.");
  assert.equal(harness.calls.filter(call => call.method === "PUT").length, 1, "the debounce cannot write after finalize");
  assert.equal(harness.session(), "COMPLETED");
  assert.equal(harness.record(), "FINAL");

  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1600)); });
  assert.equal(
    harness.calls.filter(call => call.method === "PUT").length, 1,
    "the pending autosave timer was cancelled before the record finalized"
  );
  assert.equal(buttonByText(root, "Mark as done"), undefined, "the completed session hides the header action");
  assert.ok(buttonByText(root, "Reopen for editing"), "the finalized COMPLETED record is reopenable");
});

test("an already-final record completes without another record save", async t => {
  const harness = markDoneHarness(t, { initialRecord: "FINAL" });
  const root = await mountCounselor(t);

  await act(async () => { await buttonByText(root, "Mark as done").props.onClick(); });
  await settle();

  assert.equal(harness.calls.filter(call => call.method === "PUT").length, 0);
  assert.ok(harness.calls.some(call => call.method === "POST" && call.path.endsWith("/mark-done")));
  assert.equal(harness.session(), "COMPLETED");
});

test("a failed record load does not offer Mark as done", async t => {
  markDoneHarness(t, { recordFailure: true });
  const root = await mountCounselor(t);

  assert.equal(buttonByText(root, "Mark as done"), undefined);
  assert.ok(buttonByText(root, "Mark no-show"), "no-show is independent of the record load");

  await act(async () => buttonByText(root, "Session record").props.onClick());
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });

  const alerts = root.root.findAllByProps({ role: "alert" }).map(textContent).join(" ");
  assert.ok(alerts.includes("session record could not be loaded"));
  assert.ok(buttonByText(root, "Reload record"), "a failed load can be retried without leaving the page");
});

test("incomplete assessment keeps the appointment confirmed and names the fields", async t => {
  const harness = markDoneHarness(t, {
    onMarkDone: () => json({
      error: {
        code: "RECORD_INCOMPLETE",
        message: "Complete every assessment field before marking the session done.",
        details: { fields: ["plan"] },
      },
    }, 409),
  });
  const root = await mountCounselor(t);

  await act(async () => { await buttonByText(root, "Mark as done").props.onClick(); });
  await settle();

  const alerts = root.root.findAllByProps({ role: "alert" }).map(textContent).join(" ");
  assert.ok(alerts.includes("marking the session done"));
  assert.ok(alerts.includes("Plan / recommendation"));
  assert.ok(buttonByText(root, "Record"), "the page switched to the Record view");
  assert.equal(harness.session(), "CONFIRMED");
  assert.equal(harness.record(), "DRAFT");
  assert.ok(buttonByText(root, "Mark as done"), "the action stays available to retry");
  assert.equal(buttonByText(root, "Reopen for editing"), undefined);
});
