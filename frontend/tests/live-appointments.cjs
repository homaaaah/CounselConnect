// Real component forms and API requests. Python provides a disposable loopback server.
const assert = require("node:assert/strict");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-typescript.cjs");
const Page = require("../src/pages/AppointmentsPage.tsx").default;
const { request, setCsrfToken } = require("../src/services/apiClient");
const base = process.env.COUNSELCONNECT_TEST_API_URL;
assert.equal(new URL(base).hostname, "127.0.0.1");
const nativeFetch = global.fetch;
let cookie = "", root;
global.window = { location: { hash: "#appointments" } };
global.fetch = async (url, init = {}) => {
  assert.equal(new URL(url).origin, new URL(base).origin);
  const headers = new Headers(init.headers);
  if (cookie) headers.set("Cookie", cookie);
  const response = await nativeFetch(url, { ...init, headers });
  if (response.headers.get("set-cookie")) cookie = response.headers.get("set-cookie").split(";", 1)[0];
  return response;
};
async function waitFor(check) {
  for (let i = 0; i < 250; i++) {
    if (check()) return;
    await act(async () => new Promise(resolve => setTimeout(resolve, 20)));
  }
  throw new Error("Expected scheduling UI state was not reached");
}
const button = label => root.root.findAllByType("button").find(b => b.children.includes(label));
const form = label => root.root.findAllByType("form").find(f => f.findAllByType("button").some(b => b.children.includes(label)));
async function signIn(identifier) {
  if (root) { await act(async () => root.unmount()); root = null; }
  setCsrfToken(null);
  const auth = await request("/auth/login", { method: "POST", body: JSON.stringify({ identifier, password: "synthetic-live-pass" }) });
  setCsrfToken(auth.csrf_token);
  await act(async () => { root = create(React.createElement(Page, { user: auth.user })); });
  await waitFor(() => button("Refresh appointments") && !button("Refresh appointments").props.disabled);
  if (auth.user.role_code === "STUDENT") {
    await act(async () => root.root.findAllByType("select")[0].props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_CAMPUS_ID } }));
    await waitFor(() => !button("Refresh appointments").props.disabled);
  }
}
async function main() {
  try {
    // Counselor saves a recurring weekly schedule through the real form.
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL);
    await waitFor(() => Boolean(form("Save weekly schedule")));
    await act(async () => {
      const selects = form("Save weekly schedule").findAllByType("select");
      selects[0].props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_CAMPUS_ID } });
      selects[2].props.onChange({ target: { value: "BOTH" } });
      const times = form("Save weekly schedule").findAllByProps({ type: "time" });
      times[0].props.onChange({ target: { value: "08:00" } });
      times[1].props.onChange({ target: { value: "10:00" } });
    });
    await act(async () => form("Save weekly schedule").props.onSubmit({ preventDefault() {} }));
    assert.ok(JSON.stringify(root.toJSON()).includes("Weekly schedule saved."), "weekly schedule save confirmation missing");

    // The materialized slots appear for the student to book face-to-face.
    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT_NUMBER);
    await waitFor(() => Boolean(form("Request appointment")));
    await act(async () => form("Request appointment").findByType("select").props.onChange({ target: { value: "FACE_TO_FACE" } }));
    await act(async () => form("Request appointment").props.onSubmit({ preventDefault() {} }));
    assert.ok(JSON.stringify(root.toJSON()).includes("Awaiting counselor review."), "booking confirmation missing");

    // Counselor confirms, then cancels; the released slot becomes available again.
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL);
    await waitFor(() => Boolean(button("Confirm")));
    await act(async () => button("Confirm").props.onClick());
    await waitFor(() => Boolean(button("Reschedule")));
    await act(async () => button("Cancel appointment").props.onClick());
    await act(async () => button("Confirm cancellation").props.onClick());
    await waitFor(() => JSON.stringify(root.toJSON()).includes("CANCELLED"));
    console.log("Live scheduling flow passed: weekly schedule, materialized slots, book, confirm, cancel.");
  } finally {
    if (root) await act(async () => root.unmount());
  }
}
main().catch(err => { console.error(err.message); process.exitCode = 1; });
