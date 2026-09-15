const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const RegisterPage = require("../src/pages/RegisterPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient.js");

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "Content-Type": "application/json" },
});

const envelope = (items) => ({ items, page: 1, page_size: items.length || 1, total: items.length });

test("registration keeps available reference data and retries a failed program lookup", async (t) => {
  let programAttempts = 0;
  setCsrfToken(null);
  t.mock.method(global, "fetch", async (url) => {
    const path = new URL(url, "http://localhost:5173").pathname;
    if (path.endsWith("/accounts/campuses")) {
      return json(envelope([{ campus_id: 1, campus_name: "Main" }]));
    }
    if (path.endsWith("/accounts/programs")) {
      return programAttempts++ === 0
        ? json({ error: { code: "PROGRAMS_UNAVAILABLE", message: "Programs are unavailable." } }, 503)
        : json(envelope([{ program_id: 2, program_name: "BS Psychology" }]));
    }
    return json({});
  });
  let root;
  await act(async () => { root = create(React.createElement(RegisterPage)); });
  t.after(async () => { await act(async () => root.unmount()); });
  let rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Could not load programs. Please retry."));
  assert.ok(rendered.includes("Main"), "loaded campus choices remain visible");
  const retry = root.root.findAllByType("button").find((button) => button.children.includes("Retry options"));
  await act(async () => { retry.props.onClick(); });
  rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("BS Psychology"), "the program list is restored after retry");
  assert.ok(!rendered.includes("Could not load programs. Please retry."));
});
