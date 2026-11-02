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
  const root = await mountPanel(t, { observationCapture: () => ({ frame: true }), ...overrides });
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

const observationMessage = (event, requestId, extra = {}) => ({
  type: "facial-observation",
  version: 1,
  event,
  request_id: requestId,
  ...extra,
});

const observationSlot = (requestId, seq, movements = ["smile"]) => observationMessage("observation", requestId, {
  seq,
  elapsed_ms: seq * 1000,
  valid: true,
  movements,
  unavailable_reason: null,
});

const suggestionMessage = (requestId, seq, expression = null, reason = null) => observationMessage(
  "suggestion",
  requestId,
  {
    seq,
    suggested_expression: expression,
    unavailable_reason: expression ? null : (reason ?? "SUGGESTION_UNAVAILABLE"),
  },
);

test("student consents to facial observation and never sees results", async t => {
  const detections = [];
  const { root, socket } = await connectedPanel(t, {
    role: "STUDENT",
    observationDetector: async () => {
      detections.push(Date.now());
      return { valid: true, movements: ["smile"], unavailable_reason: null };
    },
  });
  await act(async () => { socket.message(observationMessage("request", "req-1")); });
  await flush();
  assert.equal(byLabel(root, "Facial observation").props["aria-expanded"], true);
  assert.ok(button(root, "Allow for this session"));
  assert.equal(detections.length, 0);
  assert.equal(socket.sent.some(message => message.type === "facial-observation"), false);

  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();
  await flush();
  const messages = socket.sent.filter(message => message.type === "facial-observation");
  assert.deepEqual(messages[0], observationMessage("consent", "req-1"));
  assert.equal(messages[1].event, "observation");
  assert.equal(messages[1].seq, 0);
  assert.equal(messages[1].valid, true);
  assert.deepEqual(messages[1].movements, ["smile"]);
  assert.equal(messages.some(message => message.event === "suggestion"), false);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Smile"));
  assert.equal(byLabel(root, "Facial observation").props.title, "Facial observations are active");
  assert.ok(button(root, "Stop sharing"));

  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  await flush();
  assert.deepEqual(socket.sent.at(-1), observationMessage("stop", "req-1"));
});

test("student sends a separate short-lag suggestion after movement", async t => {
  const { root, socket } = await connectedPanel(t, {
    role: "STUDENT",
    observationDetector: async () => ({ valid: true, movements: ["smile"], unavailable_reason: null }),
    observationSuggestionsEnabled: true,
    observationSuggestionDetector: () => new Promise(resolve => {
      setTimeout(() => resolve({ suggested_expression: "happy", unavailable_reason: null }), 1_300);
    }),
  });
  await act(async () => { socket.message(observationMessage("request", "req-1")); });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("separate local expression suggestion"));
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();
  await flush();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 1_400)); });
  const messages = socket.sent.filter(message => message.type === "facial-observation");
  const observationIndex = messages.findIndex(message => message.event === "observation");
  const suggestionIndex = messages.findIndex(message => message.event === "suggestion");
  assert.ok(observationIndex >= 0);
  assert.ok(suggestionIndex > observationIndex);
  assert.equal(messages[suggestionIndex].seq, 0);
  assert.equal(messages[suggestionIndex].suggested_expression, "happy");
  assert.ok(!JSON.stringify(root.toJSON()).includes("Suggested expression"));
  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  await flush();
});

test("counselor sees suggestions separately from movements", async t => {
  const { root, socket } = await connectedPanel(t, {
    role: "COUNSELOR",
    peerRole: "STUDENT",
    observationSuggestionsEnabled: true,
  });
  await act(async () => { byLabel(root, "Facial observation").props.onClick(); });
  await act(async () => { button(root, "Request facial observations").props.onClick(); });
  const request = socket.sent.find(message => message.type === "facial-observation");
  await act(async () => { socket.message(observationMessage("consent", request.request_id)); });
  await flush();
  await act(async () => {
    socket.message(observationSlot(request.request_id, 0));
    socket.message(suggestionMessage(request.request_id, 0, "happy"));
  });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Suggested expression"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Happy"));

  await act(async () => {
    socket.message(observationSlot(request.request_id, 1, []));
    socket.message(observationSlot(request.request_id, 2));
    socket.message(suggestionMessage(request.request_id, 2, "sad"));
  });
  await flush();
  await act(async () => { button(root, "Finish observations and review").props.onClick(); });
  await flush();
  const text = JSON.stringify(root.toJSON());
  assert.ok(text.includes("Suggested expressions (estimates)"));
  assert.ok(text.includes("Movements detected"));
  assert.ok(text.includes("Suggested expression"));
  assert.ok(text.includes("Happy"));
  assert.ok(text.includes("Sad"));
  assert.ok(text.includes("View details"));
  assert.ok(text.includes("These are estimates based on facial appearance"));
  assert.ok(text.includes("Facial observation summary"));
});

test("counselor finishes the movement review and latest invalid clears the current movement", async t => {
  const { root, socket } = await connectedPanel(t, { role: "COUNSELOR", peerRole: "STUDENT" });
  await act(async () => { byLabel(root, "Facial observation").props.onClick(); });
  await act(async () => { button(root, "Request facial observations").props.onClick(); });
  const request = socket.sent.find(message => message.type === "facial-observation");
  await act(async () => { socket.message(observationMessage("consent", request.request_id)); });
  await flush();
  for (let seq = 0; seq < 30; seq += 1) {
    await act(async () => { socket.message(observationSlot(request.request_id, seq)); });
    await flush();
  }
  assert.ok(JSON.stringify(root.toJSON()).includes("Latest check"));
  await act(async () => {
    socket.message(observationMessage("observation", request.request_id, {
      seq: 30, elapsed_ms: 30_000, valid: false, movements: [], unavailable_reason: "CAMERA_OFF",
    }));
  });
  await flush();
  const latest = textOf(root.root.findByProps({ "data-testid": "latest-check" }));
  assert.ok(latest.includes("No tracked movement"));
  assert.ok(latest.includes("Camera off"));
  assert.ok(!latest.includes("Smile"));

  await act(async () => { button(root, "Finish observations and review").props.onClick(); });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Facial observation summary"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Sustained events:"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Temporary timeline"));
});

test("student finish, tab hiding, and detector failure keep the call usable", async t => {
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  const listeners = {};
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (type, listener) => { listeners[type] = listener; },
    removeEventListener: (type, listener) => { if (listeners[type] === listener) delete listeners[type]; },
  };
  t.after(() => {
    if (previousDocument) Object.defineProperty(globalThis, "document", previousDocument);
    else delete globalThis.document;
  });

  const { root, socket } = await connectedPanel(t, {
    role: "STUDENT",
    observationDetector: async () => ({ valid: true, movements: ["smile"], unavailable_reason: null }),
  });
  await act(async () => { socket.message(observationMessage("request", "req-1")); });
  await flush();
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();
  await flush();
  document.visibilityState = "hidden";
  await act(async () => { listeners.visibilitychange(); });
  await flush();
  assert.deepEqual(socket.sent.at(-1), observationMessage("stop", "req-1"));
  assert.equal(button(root, "Stop sharing"), undefined);

  await act(async () => {
    root.update(React.createElement(AppointmentCallPanel, { ...props, role: "GUIDANCE_STAFF" }));
  });
  assert.equal(byLabel(root, "Facial observation"), undefined);
});
