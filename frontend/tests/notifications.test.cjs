const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const { ToastProvider, useToast } = require("../src/components/feedback/Notifications.jsx");

function Trigger() {
  const toast = useToast();
  return React.createElement(
    "div",
    null,
    React.createElement("button", { type: "button", onClick: () => toast.error("Boom went the request") }, "error"),
    React.createElement("button", { type: "button", onClick: () => toast.success("Saved fine") }, "success"),
  );
}

async function mount(t) {
  let root;
  await act(async () => {
    root = create(React.createElement(ToastProvider, null, React.createElement(Trigger)));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

const clickButton = (root, label) =>
  act(async () => {
    root.root.findAllByType("button").find((b) => b.children.join("") === label).props.onClick();
  });

test("errors render as a visual alert and can be dismissed", async (t) => {
  const root = await mount(t);
  await clickButton(root, "error");
  const rendered = JSON.stringify(root.toJSON());
  assert.match(rendered, /Boom went the request/);
  assert.ok(root.root.findAllByProps({ role: "alert" }).length >= 1, "error uses role=alert");

  const dismiss = root.root.findAllByProps({ "aria-label": "Dismiss notification" })[0];
  assert.ok(dismiss, "notification is dismissible");
  await act(async () => { dismiss.props.onClick(); });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Boom went the request"), "dismiss removes it");
});

test("non-error notifications are announced as status", async (t) => {
  const root = await mount(t);
  await clickButton(root, "success");
  assert.ok(root.root.findAllByProps({ role: "status" }).length >= 1);
  assert.match(JSON.stringify(root.toJSON()), /Saved fine/);
});
