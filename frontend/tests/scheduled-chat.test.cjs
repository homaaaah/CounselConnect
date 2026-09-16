const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");

const ScheduledSessionPage = require("../src/pages/ScheduledSessionPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient");

const user = { user_id: 2, role_code: "STUDENT", account_status: "ACTIVE" };
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

test("scheduled session explicitly joins, catches up, and persists a message", async t => {
  const now = Date.now();
  let joined = false;
  const calls = [];
  global.window = {
    location: { origin: "http://localhost:5173", hash: "#session/7" },
    addEventListener() {},
    removeEventListener() {},
  };
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    calls.push({ path, ...init });
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json({
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
          can_cancel: false,
          can_reschedule: false,
          can_change_mode: false,
        },
      });
    }
    if (path.endsWith("/appointments/7/session/join")) {
      joined = true;
      return json({ conversation_id: 11 });
    }
    if (path.endsWith("/conversations/11/messages") && init.method === "POST") {
      const request = JSON.parse(init.body);
      return json({
        message_id: 21,
        conversation_id: 11,
        sender_user_id: 2,
        client_message_id: request.client_message_id,
        sequence_number: 1,
        body: request.body,
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
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  t.after(async () => { await act(async () => root.unmount()); });

  const join = root.root.findAllByType("button").find(button =>
    button.children.includes("Join scheduled session")
  );
  assert.ok(join);
  await act(async () => {
    await join.props.onClick();
    await new Promise(resolve => setTimeout(resolve, 0));
  });

  const textarea = root.root.findByType("textarea");
  await act(async () => textarea.props.onChange({ target: { value: "Hello counselor" } }));
  const form = root.root.findByType("form");
  await act(async () => form.props.onSubmit({ preventDefault() {} }));

  const sent = calls.find(call => call.path.endsWith("/conversations/11/messages") && call.method === "POST");
  assert.equal(JSON.parse(sent.body).body, "Hello counselor");
  assert.ok(JSON.stringify(root.toJSON()).includes("Hello counselor"));
});

test("counselor can join a conversation the student opened first", async t => {
  const now = Date.now();
  let counselorJoined = false;
  global.window = {
    location: { origin: "http://localhost:5173", hash: "#session/7" },
    addEventListener() {},
    removeEventListener() {},
  };
  setCsrfToken("synthetic-csrf");
  t.after(() => setCsrfToken(null));
  t.mock.method(global, "fetch", async (url, init = {}) => {
    const path = new URL(url, window.location.origin).pathname;
    if (path.endsWith("/appointments/7/session") && (!init.method || init.method === "GET")) {
      return json({
        appointment_id: 7, conversation_id: 11, appointment_mode: "ONLINE", status: "CONFIRMED",
        starts_at: new Date(now - 60_000).toISOString(), ends_at: new Date(now + 3_600_000).toISOString(),
        lobby_opens_at: new Date(now - 1_800_000).toISOString(), messaging_opens_at: new Date(now - 60_000).toISOString(),
        safety_deadline_at: new Date(now + 4_500_000).toISOString(), server_time: new Date(now).toISOString(),
        student_joined_at: new Date(now - 30_000).toISOString(), counselor_joined_at: counselorJoined ? new Date(now).toISOString() : null,
        conversation_status: "OPEN", closure_reason: null,
        capabilities: { can_open_lobby: true, can_join: !counselorJoined, can_send: counselorJoined, can_read_history: counselorJoined, can_cancel: false, can_reschedule: false, can_change_mode: false },
      });
    }
    if (path.endsWith("/appointments/7/session/join")) {
      counselorJoined = true;
      return json({ conversation_id: 11 });
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
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  t.after(async () => { await act(async () => root.unmount()); });

  const join = root.root.findAllByType("button").find(button =>
    button.children.includes("Join scheduled session")
  );
  assert.ok(join);
  await act(async () => {
    await join.props.onClick();
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  assert.equal(counselorJoined, true);
});
