const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const App = require("../src/App.jsx").default;
const AppNavBar = require("../src/components/layout/AppNavBar.jsx").default;
const LandingPage = require("../src/pages/LandingPage.jsx").default;
const { setCsrfToken } = require("../src/services/apiClient.js");

const baseUser = { user_id: 1, email: "counselor@example.edu", role_code: "COUNSELOR",
  account_status: "ACTIVE", first_name: "Cora", last_name: "Reyes" };
const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

const authFor = (user) => ({ user, csrf_token: "synthetic-csrf-token",
  idle_expires_at: "2099-01-01T01:00:00Z", absolute_expires_at: "2099-01-01T12:00:00Z" });

function environment(t, initialHash = "#home") {
  const events = new EventTarget();
  let hash = initialHash;
  const location = { reload: t.mock.fn() };
  Object.defineProperty(location, "hash", {
    get: () => hash,
    set: (value) => { hash = value; events.dispatchEvent(new Event("hashchange")); },
  });
  global.window = { location, open: t.mock.fn(),
    addEventListener: events.addEventListener.bind(events),
    removeEventListener: events.removeEventListener.bind(events) };
  setCsrfToken(null);
  t.after(() => { setCsrfToken(null); });
}

function fakeApi(t, auth) {
  const calls = [];
  t.mock.method(global, "fetch", async (url, init = {}) => {
    calls.push({ path: new URL(url, "http://localhost:5173").pathname, ...init });
    if (url.endsWith("/auth/csrf")) return json(auth);
    if (url.endsWith("/auth/logout")) return new Response(null, { status: 204 });
    if (url.endsWith("/health")) return json({ status: "ok" });
    return json({ items: [] });
  });
  return calls;
}

async function mount(t, component) {
  let root;
  await act(async () => { root = create(component); });
  t.after(async () => { await act(async () => { await root.unmount(); }); });
  return root;
}

test("counselor sidebar shows greeting, role chip, active Dashboard, Users, and Appointments links", async (t) => {
  environment(t);
  fakeApi(t, authFor(baseUser));
  const root = await mount(t, React.createElement(App));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Cora"));
  assert.ok(rendered.includes("Reyes"));
  assert.ok(rendered.includes("Counselor"));
  assert.ok(rendered.includes("Dashboard"));
  assert.ok(rendered.includes("Users"));
  assert.ok(rendered.includes("Library"));
  assert.ok(rendered.includes("Settings"));
  // Dashboard (#home) is the current page with the sidebar role label.
  const active = root.root.findAllByProps({ "aria-current": "page" });
  assert.ok(active.length >= 1);
  for (const node of active) {
    const text = node.children.map((c) => (typeof c === "string" ? c : "")).join("").trim();
    assert.equal(text, "Dashboard");
  }
  assert.ok(root.root.findAllByProps({ href: "#appointments" }).length >= 1);
  assert.ok(root.root.findAllByProps({ href: "#review" }).length >= 1);
  assert.ok(root.root.findAllByType("button").some((b) => b.children.includes("Sign out")));
  // Library and Settings have no routes yet — disabled placeholders.
  const soon = root.root.findAllByProps({ "aria-disabled": "true" })
    .filter((node) => node.props.title === "Coming soon");
  const soonLabels = soon.map((node) => node.children.map((c) => (typeof c === "string" ? c : "")).join("").trim());
  assert.ok(soonLabels.some((label) => label.includes("Library")), "Library is a coming-soon entry");
  assert.ok(soonLabels.some((label) => label.includes("Settings")), "Settings is a coming-soon entry");
  for (const node of soon) assert.equal(node.props.href, undefined);
});

test("active student sees Appointments link; Messages/Resources render unclickable, SOS/Assistant gone", async (t) => {
  environment(t);
  const student = { ...baseUser, user_id: 2, role_code: "STUDENT",
    first_name: "Ana", last_name: "Santos" };
  fakeApi(t, authFor(student));
  const root = await mount(t, React.createElement(App));
  assert.ok(root.root.findAllByProps({ href: "#appointments" }).length >= 1);
  // Messages/Resources are visible "coming soon" entries: disabled spans
  // without href (2026-09-13); SOS/Assistant remain removed.
  const soon = root.root.findAllByProps({ "aria-disabled": "true" })
    .filter((node) => node.props.title === "Coming soon");
  const labels = soon.map((node) => node.children[0]);
  for (const label of ["Messages", "Resources"]) {
    assert.ok(labels.includes(label), label + " should render as coming soon");
  }
  for (const node of soon) {
    assert.equal(node.props.href, undefined, "coming-soon entries must not navigate");
  }
  const rendered = JSON.stringify(root.toJSON());
  for (const label of ["SOS", "Assistant"]) {
    assert.ok(!rendered.includes("\"" + label + "\""), label + " should no longer render");
  }
});

test("pending student gets no Appointments link, Verification pending chip, and the banner", async (t) => {
  environment(t);
  const pending = { ...baseUser, user_id: 2, role_code: "STUDENT",
    account_status: "PENDING_VERIFICATION", first_name: "Ana", last_name: "Santos" };
  fakeApi(t, authFor(pending));
  const root = await mount(t, React.createElement(App));
  assert.equal(root.root.findAllByProps({ href: "#appointments" }).length, 0);
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Verification pending"));
  assert.ok(rendered.includes("Verification pending — scheduling unlocks after COR approval."));
});

test("guidance staff sees Home and verification review, with no coming-soon entries or banner", async (t) => {
  environment(t);
  const staff = { ...baseUser, user_id: 3, role_code: "GUIDANCE_STAFF",
    first_name: "Guida", last_name: "Staff" };
  fakeApi(t, authFor(staff));
  const root = await mount(t, React.createElement(App));
  assert.ok(root.root.findAllByProps({ href: "#home" }).length >= 1);
  assert.equal(root.root.findAllByProps({ href: "#appointments" }).length, 0);
  assert.ok(root.root.findAllByProps({ href: "#review" }).length >= 1);
  assert.equal(root.root.findAllByProps({ "aria-disabled": "true" }).filter(
    (node) => node.props.title === "Coming soon").length, 0);
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Guidance Staff"));
  assert.ok(!rendered.includes("scheduling unlocks after COR approval"));
});

test("mobile toggle flips aria-expanded and drawer link click closes it", async (t) => {
  environment(t);
  const student = { ...baseUser, user_id: 2, role_code: "STUDENT",
    first_name: "Ana", last_name: "Santos" };
  fakeApi(t, authFor(student));
  const root = await mount(t, React.createElement(App));
  const toggle = root.root.findAllByType("button")
    .find((b) => b.props["aria-controls"] === "app-nav-links");
  assert.equal(toggle.props["aria-expanded"], false);
  await act(async () => { toggle.props.onClick(); });
  assert.equal(toggle.props["aria-expanded"], true);
  const drawer = root.root.findByProps({ id: "app-nav-links" });
  assert.equal(drawer.props.hidden, false);
  const drawerLink = drawer.findAllByProps({ href: "#appointments" })[0];
  await act(async () => { drawerLink.props.onClick(); });
  assert.equal(toggle.props["aria-expanded"], false);
  assert.equal(drawer.props.hidden, true);
});

test("landing mobile drawer opens from the hamburger and closes on link click", async (t) => {
  environment(t, "#landing");
  fakeApi(t, authFor(baseUser));
  const root = await mount(t, React.createElement(LandingPage, { onSignedIn: () => {} }));
  const toggle = root.root.findAllByType("button")
    .find((b) => b.props["aria-controls"] === "landing-mobile-nav");
  assert.equal(toggle.props["aria-expanded"], false);
  await act(async () => { toggle.props.onClick(); });
  assert.equal(toggle.props["aria-expanded"], true);
  const drawer = root.root.findByProps({ id: "landing-mobile-nav" });
  assert.equal(drawer.props.hidden, false);
  const drawerLink = drawer.findAllByProps({ href: "#faq" })[0];
  await act(async () => { drawerLink.props.onClick(); });
  assert.equal(toggle.props["aria-expanded"], false);
});

test("removed session pill: no Session ends indicator renders at any expiry", async (t) => {
  environment(t);
  const nearExpiry = new Date(Date.now() + 3 * 60_000).toISOString();
  const root = await mount(t, React.createElement(AppNavBar, {
    user: baseUser, page: "home", idleExpiresAt: nearExpiry,
    absoluteExpiresAt: "2099-01-01T12:00:00Z", onSignOut: () => {},
  }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(!rendered.includes("Session ends"));
  assert.ok(!rendered.includes("bg-amber-100 text-amber-800") || rendered.includes("Verification"));
});

test("sign out button still works without the pill and expiry props", async (t) => {
  environment(t);
  const root = await mount(t, React.createElement(AppNavBar, {
    user: baseUser, page: "home", onSignOut: () => {},
  }));
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(!rendered.includes("Session ends"));
  assert.ok(root.root.findAllByType("button").some((b) => b.children.includes("Sign out")));
});

test("landing renders FAQ link and LOG IN still opens the student login modal", async (t) => {
  environment(t, "#landing");
  fakeApi(t, authFor(baseUser));
  const root = await mount(t, React.createElement(LandingPage, { onSignedIn: () => {} }));
  assert.ok(root.root.findAllByProps({ href: "#faq" }).length >= 2); // desktop + drawer
  assert.ok(root.root.findAllByProps({ id: "faq" }).length >= 1); // section anchor
  const login = root.root.findAllByType("button").filter((b) => b.children.includes("LOG IN"));
  assert.ok(login.length >= 1);
  await act(async () => { login[0].props.onClick(); });
  assert.ok(root.root.findAllByProps({ htmlFor: "identifier" }).length >= 1);
  assert.ok(root.root.findAllByProps({ role: "dialog" }).length >= 1);
});
