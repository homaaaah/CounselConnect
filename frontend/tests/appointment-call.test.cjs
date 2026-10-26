const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const AppointmentCallPanel = require("../src/components/calls/AppointmentCallPanel.jsx").default;

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

const button = (root, label) => root.root
  .findAllByType("button")
  .find(node => node.children.filter(child => typeof child === "string").join("").trim() === label);

const byLabel = (root, label) => root.root
  .findAllByType("button")
  .find(node => node.props["aria-label"] === label);

const textOf = node => node.children
  .map(child => (typeof child === "string" ? child : textOf(child)))
  .join("");

class FakeWebSocket {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.readyState = 0;
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    FakeWebSocket.instances.push(this);
  }
  send(data) { this.sent.push(JSON.parse(data)); }
  close() { this.readyState = 3; }
  open() { this.readyState = 1; if (this.onopen) this.onopen(); }
  message(event) { if (this.onmessage) this.onmessage({ data: JSON.stringify(event) }); }
}

class FakePeerConnection {
  static instances = [];
  static holdOffer = false;
  constructor(config) {
    this.config = config;
    this.localDescription = null;
    this.remoteDescription = null;
    this.connectionState = "new";
    this.addedTracks = [];
    this.candidates = [];
    this.closed = false;
    this.releaseOffer = null;
    this.onicecandidate = null;
    this.ontrack = null;
    this.onconnectionstatechange = null;
    FakePeerConnection.instances.push(this);
  }
  addTrack(track, stream) { this.addedTracks.push({ track, stream }); }
  createOffer() {
    const offer = { type: "offer", sdp: "offer-sdp" };
    if (!FakePeerConnection.holdOffer) return Promise.resolve(offer);
    return new Promise(resolve => { this.releaseOffer = () => resolve(offer); });
  }
  async createAnswer() { return { type: "answer", sdp: "answer-sdp" }; }
  async setLocalDescription(description) { this.localDescription = description; }
  async setRemoteDescription(description) { this.remoteDescription = description; }
  async addIceCandidate(candidate) { this.candidates.push(candidate); }
  close() { this.closed = true; this.connectionState = "closed"; }
}

function installCallEnvironment(t, { denyMedia = false, holdOffer = false } = {}) {
  FakeWebSocket.instances = [];
  FakePeerConnection.instances = [];
  FakePeerConnection.holdOffer = holdOffer;
  const stopped = [];
  const mediaCalls = [];
  const tracks = [
    { kind: "audio", enabled: true, stop: () => stopped.push("audio") },
    { kind: "video", enabled: true, stop: () => stopped.push("video") },
  ];
  const stream = {
    getTracks: () => tracks,
    getAudioTracks: () => tracks.filter(track => track.kind === "audio"),
    getVideoTracks: () => tracks.filter(track => track.kind === "video"),
  };
  const remoteStream = { id: "remote-stream" };
  const navigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    writable: true,
    value: {
      mediaDevices: {
        getUserMedia: async constraints => {
          mediaCalls.push(constraints);
          if (denyMedia) {
            const error = new Error("Permission denied");
            error.name = "NotAllowedError";
            throw error;
          }
          return stream;
        },
      },
    },
  });
  globalThis.WebSocket = FakeWebSocket;
  globalThis.RTCPeerConnection = FakePeerConnection;
  global.window = {
    location: { origin: "http://localhost:5173", hash: "#session/7" },
    addEventListener() {},
    removeEventListener() {},
  };
  const fetchCalls = [];
  t.mock.method(global, "fetch", async url => {
    const path = new URL(url, window.location.origin).pathname;
    fetchCalls.push(path);
    if (path.endsWith("/appointments/7/call")) {
      return json({
        appointment_id: 7, role: "STUDENT", peer_role: "COUNSELOR", can_call: true,
        starts_at: new Date(Date.now() - 60_000).toISOString(),
        ends_at: new Date(Date.now() + 3_600_000).toISOString(),
        safety_deadline_at: new Date(Date.now() + 4_500_000).toISOString(),
        server_time: new Date().toISOString(),
        ice_servers: [{ urls: ["stun:stun.l.google.com:19302"] }],
      });
    }
    throw new Error(`Unexpected request: ${path}`);
  });
  t.after(() => {
    if (navigatorDescriptor) Object.defineProperty(globalThis, "navigator", navigatorDescriptor);
    else delete globalThis.navigator;
    delete globalThis.WebSocket;
    delete globalThis.RTCPeerConnection;
  });
  return { fetchCalls, mediaCalls, remoteStream, stopped, stream, tracks };
}

const props = {
  appointmentId: 7,
  canCall: true,
  startsAt: new Date(Date.now() - 60_000).toISOString(),
  safetyDeadlineAt: new Date(Date.now() + 4_500_000).toISOString(),
  serverTime: new Date().toISOString(),
  appointmentMode: "ONLINE",
  status: "CONFIRMED",
};

async function mountPanel(t, overrides = {}) {
  let root;
  await act(async () => {
    root = create(React.createElement(AppointmentCallPanel, { ...props, ...overrides }));
  });
  t.after(async () => { await act(async () => root.unmount()); });
  return root;
}

async function flush() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
}

async function connectedPanel(t, overrides = {}) {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t, overrides);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: overrides.peerRole ?? "COUNSELOR" });
  });
  await flush();
  const peer = FakePeerConnection.instances[0];
  await act(async () => {
    peer.connectionState = "connected";
    peer.onconnectionstatechange?.();
  });
  return { env, root, socket, peer };
}

test("join, negotiate, toggle devices, and hang up cleans up", async t => {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t);

  assert.ok(button(root, "Join video call"));
  assert.equal(env.mediaCalls.length, 0, "media is not requested on mount");

  await act(async () => {
    button(root, "Join video call").props.onClick();
  });
  await flush();

  assert.equal(env.fetchCalls.some(path => path.endsWith("/appointments/7/call")), true, "call config is fetched");
  assert.equal(env.mediaCalls.length, 1);
  assert.deepEqual(env.mediaCalls[0], { video: true, audio: true });
  const socket = FakeWebSocket.instances[0];
  assert.ok(socket.url.includes("/api/v1/appointments/7/call/ws"));

  await act(async () => { socket.open(); });
  assert.deepEqual(socket.sent[0], { type: "ready" });
  assert.ok(JSON.stringify(root.toJSON()).includes("Waiting for the other participant"));

  await act(async () => {
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  const peer = FakePeerConnection.instances[0];
  assert.ok(peer);
  assert.deepEqual(peer.config.iceServers, [{ urls: ["stun:stun.l.google.com:19302"] }]);
  assert.equal(peer.addedTracks.length, 2);
  assert.deepEqual(socket.sent.at(-1), { type: "offer", sdp: "offer-sdp" });

  await act(async () => {
    socket.message({ type: "answer", sdp: "answer-sdp" });
  });
  await flush();
  assert.deepEqual(peer.remoteDescription, { type: "answer", sdp: "answer-sdp" });

  await act(async () => {
    socket.message({ type: "ice-candidate", candidate: { candidate: "candidate:1" } });
  });
  await flush();
  assert.deepEqual(peer.candidates[0], { candidate: "candidate:1" });

  await act(async () => {
    peer.connectionState = "connected";
    peer.onconnectionstatechange?.();
    peer.ontrack?.({ streams: [env.remoteStream] });
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Connected"));

  const videos = root.root.findAllByType("video").map(node => node.props["aria-label"]);
  assert.deepEqual(videos.sort(), ["Counselor", "Your camera"], "remote video and self-view render");

  const mic = byLabel(root, "Microphone");
  assert.equal(mic.props["aria-pressed"], true);
  await act(async () => { mic.props.onClick(); });
  assert.equal(env.tracks[0].enabled, false);
  assert.equal(byLabel(root, "Microphone").props["aria-pressed"], false);
  await act(async () => { byLabel(root, "Camera").props.onClick(); });
  assert.equal(env.tracks[1].enabled, false);

  await act(async () => { byLabel(root, "End call").props.onClick(); });
  assert.deepEqual(socket.sent.at(-1), { type: "hangup" });
  assert.equal(peer.closed, true);
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.ok(button(root, "Rejoin call"));
  assert.ok(JSON.stringify(root.toJSON()).includes("You left the call"));
});

test("connection failure cleans up and offers a retry", async t => {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  const peer = FakePeerConnection.instances[0];
  await act(async () => {
    peer.connectionState = "failed";
    peer.onconnectionstatechange?.();
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("could not connect"));
  assert.equal(peer.closed, true);
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.ok(button(root, "Try again"));
});

test("peer departure ends the call and cleans up", async t => {  const env = installCallEnvironment(t);
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  await act(async () => { socket.message({ type: "peer-left" }); });
  assert.ok(JSON.stringify(root.toJSON()).includes("The other participant left the call"));
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.equal(FakePeerConnection.instances[0].closed, true);
});

test("device denial shows an alert and never opens a socket", async t => {
  const env = installCallEnvironment(t, { denyMedia: true });
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();

  const alerts = root.root.findAllByProps({ role: "alert" });
  assert.ok(alerts.some(node => JSON.stringify(node.children).includes("access was blocked")));
  assert.equal(FakeWebSocket.instances.length, 0);
  assert.ok(button(root, "Try again"));
  assert.equal(env.mediaCalls.length, 1);
});

test("a late offer after hang-up is discarded", async t => {
  installCallEnvironment(t, { holdOffer: true });
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  const peer = FakePeerConnection.instances[0];
  assert.ok(peer, "the pending offer created a peer connection");

  await act(async () => { byLabel(root, "End call").props.onClick(); });
  await act(async () => { peer.releaseOffer(); });
  await flush();

  assert.ok(JSON.stringify(root.toJSON()).includes("You left the call"));
  assert.equal(socket.sent.some(message => message.type === "offer"), false);
});

test("signaling socket close ends the call and stops tracks", async t => {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  await act(async () => { socket.onclose?.(); });
  assert.ok(JSON.stringify(root.toJSON()).includes("The call ended"));
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.ok(button(root, "Rejoin call"));
});

test("window close during a call ends it", async t => {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t);
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => {
    socket.open();
    socket.message({ type: "room-state", peer_present: true, initiator: true, peer_role: "COUNSELOR" });
  });
  await flush();
  await act(async () => {
    root.update(React.createElement(AppointmentCallPanel, {
      ...props,
      canCall: false,
      serverTime: new Date(Date.now() + 5_000_000).toISOString(),
    }));
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("The video call window has ended"));
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.equal(byLabel(root, "End call"), undefined);
});

test("unmount stops tracks and closes the signaling socket", async t => {
  const env = installCallEnvironment(t);
  let root;
  await act(async () => {
    root = create(React.createElement(AppointmentCallPanel, props));
  });
  await act(async () => { button(root, "Join video call").props.onClick(); });
  await flush();
  const socket = FakeWebSocket.instances[0];
  await act(async () => { socket.open(); });
  await act(async () => { root.unmount(); });
  assert.deepEqual([...env.stopped].sort(), ["audio", "video"]);
  assert.equal(socket.readyState, 3);
});

test("face-to-face appointment does not claim the call opens", async t => {
  installCallEnvironment(t);
  const root = await mountPanel(t, {
    canCall: false,
    appointmentMode: "FACE_TO_FACE",
    status: "CONFIRMED",
  });
  const rendered = JSON.stringify(root.toJSON());
  assert.ok(rendered.includes("Video call is unavailable for this appointment"));
  assert.ok(!rendered.includes("Video call opens at"));
});

test("outside the call window shows a message and does not request media", async t => {
  const env = installCallEnvironment(t);
  const root = await mountPanel(t, {
    canCall: false,
    startsAt: new Date(Date.now() + 3_600_000).toISOString(),
    serverTime: new Date().toISOString(),
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Video call opens at"));
  assert.equal(env.mediaCalls.length, 0);
  assert.equal(button(root, "Join video call"), undefined);
});

test("student allows the live cue and shares only a label and confidence", async t => {
  const scans = [];
  const { root, socket } = await connectedPanel(t, {
    role: "STUDENT",
    expressionScan: async () => {
      scans.push(Date.now());
      return { label: "happy", confidence: 0.81 };
    },
  });

  await act(async () => {
    socket.message({ type: "expression", event: "request", id: "req-1" });
  });
  await flush();
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], true, "a request opens the popup");
  assert.ok(button(root, "Allow for this session"));
  assert.equal(scans.length, 0, "a request never auto-scans");
  assert.equal(socket.sent.some(message => message.type === "expression"), false);

  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();

  const expressionMessages = socket.sent.filter(message => message.type === "expression");
  assert.deepEqual(expressionMessages[0], { type: "expression", event: "consent", id: "req-1" });
  assert.deepEqual(expressionMessages[1], {
    type: "expression", event: "result", id: "req-1", label: "happy", confidence: 0.81,
  });
  assert.equal(scans.length, 1);
  assert.ok(
    !JSON.stringify(root.toJSON()).includes("Happy (81% confidence)"),
    "the Student never sees the result",
  );
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], false, "accepting closes the popup");
  assert.equal(byLabel(root, "Expression cue").props.title, "Expression cue is live");
  assert.equal(root.root.findAllByProps({ "data-testid": "expression-cue-badge" }).length, 0);
  assert.ok(button(root, "Stop sharing"), "closing keeps the live panel mounted");

  const resultsBeforeClose = socket.sent.filter(message => message.event === "result").length;
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 2300)); });
  const resultsAfterClose = socket.sent.filter(message => message.event === "result").length;
  assert.equal(resultsAfterClose, resultsBeforeClose + 1, "the scan continues while closed");

  const beforeReopen = socket.sent.length;
  await act(async () => { byLabel(root, "Expression cue").props.onClick(); });
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], true);
  assert.equal(socket.sent.length, beforeReopen, "reopening sends nothing");

  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  await flush();
  assert.deepEqual(socket.sent.at(-1), { type: "expression", event: "stop" });
  assert.equal(byLabel(root, "Expression cue").props.title, "Hide expression cue");
  assert.equal(root.root.findAllByProps({ "data-testid": "expression-cue-badge" }).length, 0);
});

test("counselor starts the live cue, sees updates, and stops", async t => {
  const { root, socket } = await connectedPanel(t, { role: "COUNSELOR", peerRole: "STUDENT" });

  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], false);
  await act(async () => { byLabel(root, "Expression cue").props.onClick(); });
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], true);
  const popover = root.root.findByProps({ id: "expression-cue-popover" });
  assert.equal(popover.props.tabIndex, -1);
  assert.equal(popover.props["aria-labelledby"], "expression-cue-heading");
  await act(async () => {
    popover.props.onKeyDown({ key: "Escape" });
  });
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], false);
  await act(async () => { byLabel(root, "Expression cue").props.onClick(); });
  assert.ok(button(root, "Start live expression cue"));
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  const request = socket.sent.find(message => message.type === "expression");
  assert.equal(request.event, "request");
  assert.ok(request.id.length >= 1 && request.id.length <= 64);

  await act(async () => {
    socket.message({ type: "expression", event: "consent", id: request.id });
  });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("allowed the live cue"));
  assert.equal(byLabel(root, "Expression cue").props["aria-expanded"], false, "consent closes the popup");
  assert.equal(byLabel(root, "Expression cue").props.title, "Expression cue is live");

  await act(async () => {
    socket.message({
      type: "expression", event: "result", id: request.id, label: "neutral", confidence: 0.72,
    });
  });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("fa-face-meh"));
  assert.ok(JSON.stringify(root.toJSON()).includes("not diagnostic accuracy"));
  assert.match(
    textOf(root.root.findByProps({ "data-testid": "expression-cue-badge" })),
    /Live student cue: Neutral \(72% confidence\)/,
  );

  await act(async () => {
    socket.message({
      type: "expression", event: "result", id: request.id, label: "happy", confidence: 0.81,
    });
  });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Happy (81% confidence)"));
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
  assert.match(
    textOf(root.root.findByProps({ "data-testid": "expression-cue-badge" })),
    /Live student cue: Happy \(81% confidence\)/,
  );

  await act(async () => { byLabel(root, "Expression cue").props.onClick(); });
  await act(async () => { button(root, "Stop").props.onClick(); });
  await flush();
  assert.deepEqual(socket.sent.at(-1), { type: "expression", event: "stop" });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Happy (81% confidence)"));
  assert.equal(byLabel(root, "Expression cue").props.title, "Hide expression cue");
  assert.equal(root.root.findAllByProps({ "data-testid": "expression-cue-badge" }).length, 0);
});

test("expression stop and unknown roles do not leak UI or messages", async t => {
  const { root, socket } = await connectedPanel(t, {
    role: "COUNSELOR",
    peerRole: "STUDENT",
    expressionScan: async () => null,
  });

  await act(async () => { byLabel(root, "Expression cue").props.onClick(); });
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  const request = socket.sent.find(message => message.type === "expression");
  await act(async () => {
    socket.message({ type: "expression", event: "result", id: request.id, label: "sad", confidence: 0.7 });
  });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Sad (70% confidence)"));

  await act(async () => {
    socket.message({ type: "expression", event: "stop" });
  });
  await flush();
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sad (70% confidence)"));

  await act(async () => {
    root.update(React.createElement(AppointmentCallPanel, { ...props, role: "GUIDANCE_STAFF" }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Expression cue"));
  assert.equal(byLabel(root, "Expression cue"), undefined);
  assert.equal(button(root, "Start live expression cue"), undefined);
});
