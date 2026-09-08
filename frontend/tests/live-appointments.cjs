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
  if (auth.user.role_code === "STUDENT") {
    await act(async () => root.root.findAllByType("select")[0].props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_CAMPUS_ID } }));
    await waitFor(() => !button("Refresh appointments").props.disabled);
  }
}
async function main() {
  try {
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL);
    await act(async () => root.root.findAllByType("select")[0].props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_CAMPUS_ID } }));
    const dates = form("Create slots").findAllByProps({ type: "datetime-local" });
    await act(async () => {
      dates[0].props.onChange({ target: { value: "2099-01-01T09:00" } });
      dates[1].props.onChange({ target: { value: "2099-01-01T11:00" } });
      form("Create slots").findByProps({ type: "number" }).props.onChange({ target: { value: "60" } });
      form("Create slots").findByType("select").props.onChange({ target: { value: "BOTH" } });
    });
    await act(async () => form("Create slots").props.onSubmit({ preventDefault() {} }));
    assert.ok(JSON.stringify(root.toJSON()).includes("Availability slots created."));
    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT_NUMBER);
    await act(async () => form("Request appointment").findByType("select").props.onChange({ target: { value: "FACE_TO_FACE" } }));
    await act(async () => form("Request appointment").props.onSubmit({ preventDefault() {} }));
    assert.ok(JSON.stringify(root.toJSON()).includes("Awaiting counselor review."));
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL);
    await act(async () => button("Confirm").props.onClick());
    await waitFor(() => Boolean(button("Reschedule")));
    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT_NUMBER);
    await act(async () => button("Reschedule").props.onClick());
    await act(async () => form("Choose replacement").findByType("select").props.onChange({ target: { value: "FACE_TO_FACE" } }));
    await act(async () => form("Choose replacement").props.onSubmit({ preventDefault() {} }));
    assert.ok(JSON.stringify(root.toJSON()).includes("Rescheduled."));
    await signIn(process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL);
    await act(async () => button("Confirm").props.onClick());
    await waitFor(() => Boolean(button("Reschedule")));
    await signIn(process.env.COUNSELCONNECT_TEST_STUDENT_NUMBER);
    await act(async () => button("Cancel appointment").props.onClick());
    await act(async () => button("Confirm cancellation").props.onClick());
    await waitFor(() => JSON.stringify(root.toJSON()).includes("CANCELLED"));
    console.log("Live scheduling flow passed: create slots, book, confirm, reschedule, reconfirm, cancel.");
  } finally {
    if (root) await act(async () => root.unmount());
  }
}
main().catch(err => { console.error(err.message); process.exitCode = 1; });
