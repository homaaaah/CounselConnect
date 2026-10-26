// Python owns the disposable loopback server, synthetic accounts and storage.
const assert = require("node:assert/strict");
const React = require("react");
const { create, act } = require("react-test-renderer");
require("./register-app.cjs");
const UsersPage = require("../src/pages/superadmin/UsersManagementPage.jsx").default;
const CorrectionsPage = require("../src/pages/superadmin/CorrectionsPage.jsx").default;
const StudentCorrections = require("../src/features/accounts/StudentCorrections.jsx").default;
const { ToastProvider } = require("../src/components/feedback");
const { request, setCsrfToken } = require("../src/services/apiClient");
const base = process.env.COUNSELCONNECT_TEST_API_URL;
assert.ok(base && new URL(base).hostname === "127.0.0.1", "Disposable loopback API required");
const nativeFetch = global.fetch;
let cookie = "", root;
global.window = { setTimeout, clearTimeout };
global.fetch = async (url, init = {}) => {
  assert.equal(new URL(url).origin, new URL(base).origin);
  const headers = new Headers(init.headers);
  if (cookie) headers.set("Cookie", cookie);
  const response = await nativeFetch(url, { ...init, headers });
  if (response.headers.get("set-cookie")) cookie = response.headers.get("set-cookie").split(";")[0];
  return response;
};
const manager = process.env.COUNSELCONNECT_TEST_MANAGER;
const student = process.env.COUNSELCONNECT_TEST_STUDENT;
const studentId = Number(process.env.COUNSELCONNECT_TEST_STUDENT_ID);
const requestId = Number(process.env.COUNSELCONNECT_TEST_REQUEST_ID);
const text = () => JSON.stringify(root.toJSON());
const button = (title) => root.root.findAllByType("button").find((node) => node.children.join("") === title);
const hasId = (id) => root.root.findAllByProps({ id }).length > 0;
async function waitFor(predicate) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (predicate()) return;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)); });
  }
  throw new Error("Expected management UI state was not reached.");
}
async function click(node) { assert.ok(node, "Expected action available"); await act(async () => { await node.props.onClick(); }); }
async function signIn(identifier, password, Component) {
  if (root) { await act(async () => root.unmount()); root = null; }
  setCsrfToken(null);
  const auth = await request("/auth/login", { method: "POST", body: JSON.stringify({ identifier, password }) });
  setCsrfToken(auth.csrf_token);
  await act(async () => { root = create(React.createElement(ToastProvider, null, React.createElement(Component, { user: auth.user }))); });
}
async function main() {
  await signIn(manager, "synthetic-ui-pass", CorrectionsPage);
  await waitFor(() => hasId(`review-open-${requestId}`));
  await click(root.root.findByProps({ id: `review-open-${requestId}` }));
  await waitFor(() => hasId(`review-return-${requestId}`));
  await click(button("Preview current COR"));
  assert.equal(root.root.findAllByType("iframe").length, 1);
  await click(root.root.findByProps({ id: `review-return-${requestId}` }));
  await act(async () => root.root.findByProps({ "aria-label": "Return reason" }).props.onChange({ target: { value: "Check section on the current COR." } }));
  await click(root.root.findByProps({ id: "confirm-correction-decision" }));
  await waitFor(() => text().includes("RETURNED"));
  assert.equal(root.root.findAllByType("iframe").length, 0);
  await signIn(student, "password1", StudentCorrections);
  await waitFor(() => hasId(`my-correction-${requestId}`));
  await click(root.root.findByProps({ id: `my-correction-${requestId}` }));
  await waitFor(() => root.root.findAllByType("form").length === 1);
  await act(async () => root.root.findByProps({ "aria-label": "Section" }).props.onChange({ target: { value: "B" } }));
  const file = new File(["%PDF-1.4 live revision"], "current.pdf", { type: "application/pdf" });
  await act(async () => root.root.findByProps({ "aria-label": "Fresh current COR PDF" }).props.onChange({ target: { files: [file] } }));
  await act(async () => root.root.findByType("form").props.onSubmit({ preventDefault() {} }));
  const studentCookie = cookie;
  await waitFor(() => text().includes("awaiting review"));
  const listing = await request("/profile-change-requests?status=PENDING");
  assert.equal(listing.total, 1);
  const revisedId = listing.items[0].change_request.change_request_id;
  assert.notEqual(revisedId, requestId);
  await signIn(manager, "synthetic-ui-pass", CorrectionsPage);
  await waitFor(() => hasId(`review-open-${revisedId}`));
  await click(root.root.findByProps({ id: `review-open-${revisedId}` }));
  await waitFor(() => hasId(`review-approve-${revisedId}`));
  await click(button("Preview current COR"));
  assert.equal(root.root.findAllByType("iframe").length, 1);
  await click(root.root.findByProps({ id: `review-approve-${revisedId}` }));
  await click(root.root.findByProps({ id: "confirm-correction-decision" }));
  await waitFor(() => text().includes("APPROVED"));
  assert.equal(root.root.findAllByType("iframe").length, 0);
  await signIn(manager, "synthetic-ui-pass", UsersPage);
  await waitFor(() => button("Next") && !button("Next").props.disabled);
  await click(button("Next"));
  await waitFor(() => hasId(`user-open-${studentId}`));
  await click(root.root.findByProps({ id: `user-open-${studentId}` }));
  await waitFor(() => hasId(`user-status-${studentId}`));
  await click(root.root.findByProps({ id: `user-status-${studentId}` }));
  await click(root.root.findByProps({ id: "confirm-user-status" }));
  await waitFor(() => Boolean(button("Reactivate account")));
  await click(button("Reactivate account"));
  await click(root.root.findByProps({ id: "confirm-user-status" }));
  await waitFor(() => Boolean(button("Deactivate account")));
  const revoked = await nativeFetch(`${base}/auth/me`, { headers: { Cookie: studentCookie } });
  assert.equal(revoked.status, 401, "Reactivation must not restore old sessions");
  await signIn(student, "password1", StudentCorrections);
  await waitFor(() => hasId(`my-correction-${revisedId}`));
  await click(root.root.findByProps({ id: `my-correction-${revisedId}` }));
  await waitFor(() => text().includes("now reflects the approved changes"));
  assert.equal(root.root.findAllByType("form").length, 0);
  await click(button("Browse complete correction history"));
  await waitFor(() => hasId(`my-correction-${requestId}`) && hasId(`my-correction-${revisedId}`));
  await act(async () => root.unmount());
  root = null;
  console.log("Real React/HTTP/MySQL Users and correction lifecycle passed.");
}
main().catch(async (error) => {
  if (root) await act(async () => root.unmount());
  console.error(error.message);
  process.exitCode = 1;
});
