// Invoked only by the isolated backend integration test. The actual React
// app and API client talk to a real FastAPI/MySQL test instance over HTTP.
const assert = require("node:assert/strict");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-typescript.cjs");
const App = require("../src/App.tsx").default;
const { setCsrfToken } = require("../src/services/apiClient.ts");

const base = process.env.COUNSELCONNECT_TEST_API_URL;
assert.ok(base && new URL(base).hostname === "127.0.0.1", "A disposable loopback API is required");
const nativeFetch = global.fetch;
let cookie = "";
global.fetch = async (url, init = {}) => {
  assert.equal(new URL(url).origin, new URL(base).origin);
  const headers = new Headers(init.headers);
  if (cookie) headers.set("Cookie", cookie);
  const response = await nativeFetch(url, { ...init, headers });
  const setCookie = response.headers.get("set-cookie");
  if (setCookie) cookie = setCookie.split(";", 1)[0];
  return response;
};
const events = new EventTarget();
let hash = "#review";
const location = {};
Object.defineProperty(location, "hash", {
  get: () => hash,
  set: (value) => { hash = value; events.dispatchEvent(new Event("hashchange")); },
});
global.window = { location, addEventListener: events.addEventListener.bind(events),
  removeEventListener: events.removeEventListener.bind(events) };

async function waitFor(predicate) {
  for (let attempt = 0; attempt < 250; attempt++) {
    if (predicate()) return;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
  }
  throw new Error("Live UI flow did not reach its expected state");
}

async function main() {
  let root;
  const button = (label) => root.root.findAllByType("button").find((item) => item.children.includes(label));
  try {
    await act(async () => { root = create(React.createElement(App)); });
    await waitFor(() => root.root.findAllByProps({ id: "identifier" }).length > 0);
    await act(async () => {
      root.root.findByProps({ id: "identifier" }).props.onChange({ target: { value: process.env.COUNSELCONNECT_TEST_COUNSELOR_EMAIL } });
      root.root.findByProps({ id: "password" }).props.onChange({ target: { value: "test-live-counselor-pass" } });
    });
    await act(async () => { await root.root.findByType("form").props.onSubmit({ preventDefault() {} }); });
    await waitFor(() => Boolean(button("Approve")));
    // Simulate a browser reload: keep only the HttpOnly cookie, lose all
    // component state and the in-memory CSRF token.
    await act(async () => { root.unmount(); });
    setCsrfToken(null);
    await act(async () => { root = create(React.createElement(App)); });
    await waitFor(() => Boolean(button("Approve")));
    await act(async () => { await button("Approve").props.onClick(); });
    await waitFor(() => JSON.stringify(root.toJSON()).includes("APPROVED"));
    await act(async () => { await button("Sign out").props.onClick(); });
    await waitFor(() => !button("Sign out"));
    assert.equal((await global.fetch(`${base}/auth/me`)).status, 401);
    console.log("Live React/API flow passed: login, reload, approve, logout");
  } finally {
    if (root) await act(async () => { root.unmount(); });
  }
}
main().catch(() => { console.error("Live React/API flow failed"); process.exitCode = 1; });
