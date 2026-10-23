const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");

const { useScheduledSessions } = require("../src/features/messaging/useScheduledSessions.js");

const json = (body) => new Response(JSON.stringify(body), {
  status: 200, headers: { "Content-Type": "application/json" },
});

function Harness({ user }) {
  useScheduledSessions(user);
  return React.createElement("div");
}

test("session_closed refreshes appointment records without broadening toast behavior", async (t) => {
  const previousWindow = global.window;
  const previousWebSocket = global.WebSocket;
  const sockets = [];
  const browserWindow = new EventTarget();
  browserWindow.location = { origin: "http://localhost:5173" };
  global.window = browserWindow;
  global.WebSocket = class FakeWebSocket {
    constructor(url) { this.url = url; sockets.push(this); }
    close() {}
  };
  t.mock.method(global, "fetch", async () => json([]));

  const updates = [];
  const toasts = [];
  browserWindow.addEventListener("appointment-updated", event => updates.push(event.detail));
  browserWindow.addEventListener("counselconnect-toast", event => toasts.push(event.detail));

  let root;
  await act(async () => {
    root = create(React.createElement(Harness, {
      user: { user_id: 2, role_code: "STUDENT", account_status: "ACTIVE" },
    }));
    await new Promise(resolve => setTimeout(resolve, 0));
  });
  t.after(async () => {
    await act(async () => root.unmount());
    global.window = previousWindow;
    global.WebSocket = previousWebSocket;
  });
  assert.equal(sockets.length, 1);

  await act(async () => sockets[0].onmessage({ data: JSON.stringify({ event: "session_closed", appointment_id: 8 }) }));
  assert.equal(updates.length, 1);
  assert.equal(updates[0].event, "session_closed");
  assert.equal(toasts.length, 0, "closing an appointment does not create a confirmation toast");

  await act(async () => sockets[0].onmessage({ data: JSON.stringify({ event: "appointment_confirmed", appointment_id: 9 }) }));
  assert.equal(updates.length, 2);
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].message, "Your appointment has been confirmed.");
});
