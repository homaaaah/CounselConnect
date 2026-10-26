const assert = require("node:assert/strict");
const { test } = require("node:test");
const React = require("react");
const { create, act } = require("react-test-renderer");

require("./register-app.cjs");

const {
  EXPRESSION_MIN_CONFIDENCE,
  aggregateExpressions,
  expressionLabelIcon,
  expressionLabelText,
  expressionResultText,
} = require("../src/features/expression/expression.js");
const ExpressionCuePanel = require("../src/components/calls/ExpressionCuePanel.jsx").default;

const button = (root, label) => root.root
  .findAllByType("button")
  .find(node => node.children.filter(child => typeof child === "string").join("").trim() === label);

const panelProps = {
  role: "STUDENT",
  localStream: { id: "local-stream" },
  camOn: true,
  phase: "connected",
  expressionEvent: null,
  sendExpression: () => {},
};

function sample(label, value = 0.8, rest = 0.2 / 6) {
  return {
    neutral: label === "neutral" ? value : rest,
    happy: label === "happy" ? value : rest,
    sad: label === "sad" ? value : rest,
    angry: label === "angry" ? value : rest,
    fearful: label === "fearful" ? value : rest,
    disgusted: label === "disgusted" ? value : rest,
    surprised: label === "surprised" ? value : rest,
  };
}

async function flush() {
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
}

function host(root, props) {
  return root.root.findAllByProps(props);
}

test("aggregation returns nothing for too few samples or weak confidence", () => {
  assert.equal(aggregateExpressions([]), null);
  assert.equal(aggregateExpressions([sample("neutral"), sample("neutral")]), null);
  assert.equal(
    aggregateExpressions([sample("neutral", 0.5), sample("neutral", 0.5), sample("neutral", 0.5)]),
    null,
  );
  assert.equal(EXPRESSION_MIN_CONFIDENCE, 0.6);
});

test("aggregation averages the ten frames and rounds the confidence", () => {
  const result = aggregateExpressions([
    sample("neutral", 0.7),
    sample("neutral", 0.72),
    sample("neutral", 0.75),
    sample("neutral", 0.75),
  ]);
  assert.deepEqual(result, { label: "neutral", confidence: 0.73 });
  assert.equal(Math.round(result.confidence * 1000) / 1000, result.confidence);
});

test("labels are observable words, never diagnostic language", () => {
  assert.equal(expressionLabelText("neutral"), "Neutral");
  assert.equal(expressionLabelText("fearful"), "Fearful");
  assert.equal(expressionLabelText("unknown"), "");
  assert.equal(
    expressionResultText({ label: "neutral", confidence: 0.723 }),
    "Neutral (72% confidence)",
  );
  assert.equal(expressionLabelIcon("neutral"), "fa-face-meh");
  assert.equal(expressionLabelIcon("surprised"), "fa-face-surprise");
  assert.equal(expressionLabelIcon("unknown"), "");
});

test("student shares the live cue without seeing the result", async () => {
  const sent = [];
  const scans = [];
  const scan = async (video, options) => {
    scans.push({ video, options });
    return { label: "neutral", confidence: 0.72 };
  };
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan,
      sendExpression: payload => sent.push(payload),
    }));
  });

  assert.equal(button(root, "Allow for this session"), undefined, "nothing is offered before a request");

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan,
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-1" },
    }));
  });
  assert.ok(button(root, "Allow for this session"));
  assert.ok(button(root, "Decline"));
  assert.equal(scans.length, 0, "a request never auto-scans");

  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();

  assert.deepEqual(sent[0], { event: "consent", id: "req-1" });
  assert.deepEqual(sent[1], {
    event: "result", id: "req-1", label: "neutral", confidence: 0.72,
  });
  assert.equal(scans.length, 1);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Live cue shared with the Counselor"));
  assert.ok(!JSON.stringify(root.toJSON()).includes("fa-face-meh"), "the Student sees no cue icon");

  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  assert.deepEqual(sent.at(-1), { event: "stop" });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
});

test("student decline sends no scan and no cue", async () => {
  const sent = [];
  let scanned = false;
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: async () => { scanned = true; return null; },
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-2" },
    }));
  });
  await act(async () => { button(root, "Decline").props.onClick(); });
  assert.deepEqual(sent, [{ event: "decline", id: "req-2" }]);
  assert.equal(scanned, false);
  assert.ok(JSON.stringify(root.toJSON()).includes("You declined the live expression cue"));
});

test("camera off disables Allow and no cue is shared without a face", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      camOn: false,
      scan: async () => null,
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-3" },
    }));
  });
  const allow = button(root, "Allow for this session");
  assert.equal(allow.props.disabled, true);
  assert.ok(JSON.stringify(root.toJSON()).includes("Turn your camera on to allow this"));

  await act(async () => { root.update(React.createElement(ExpressionCuePanel, {
    ...panelProps,
    camOn: true,
    scan: async () => null,
    sendExpression: payload => sent.push(payload),
    expressionEvent: { type: "expression", event: "request", id: "req-3" },
  })); });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();

  assert.deepEqual(sent[0], { event: "consent", id: "req-3" });
  assert.deepEqual(sent[1], { event: "unavailable", id: "req-3" });
  assert.ok(JSON.stringify(root.toJSON()).includes("No cue is currently shared"));
  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  assert.deepEqual(sent.at(-1), { event: "stop" });
});

test("scan failure shares nothing and shows a safe alert", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: async () => { throw new Error("model unavailable"); },
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-4" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();

  assert.deepEqual(sent.at(-1), { event: "unavailable", id: "req-4" });
  const alerts = host(root, { role: "alert" });
  assert.ok(alerts.some(node => JSON.stringify(node.children).includes("No cue was shared")));
  assert.ok(!JSON.stringify(root.toJSON()).includes("model unavailable"));
});

test("counselor starts the live cue, sees updates, and stops", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
    }));
  });
  assert.ok(button(root, "Start live expression cue"));
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  assert.equal(sent.length, 1);
  assert.equal(sent[0].event, "request");
  assert.equal(typeof sent[0].id, "string");
  assert.ok(sent[0].id.length >= 1 && sent[0].id.length <= 64);
  assert.ok(button(root, "Stop"));

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: sent[0].id, label: "neutral", confidence: 0.72,
      },
    }));
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("fa-face-meh"));
  assert.ok(JSON.stringify(root.toJSON()).includes("Model confidence is not diagnostic accuracy"));

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: sent[0].id, label: "happy", confidence: 0.81,
      },
    }));
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Happy (81% confidence)"));
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));

  await act(async () => { button(root, "Stop").props.onClick(); });
  assert.deepEqual(sent.at(-1), { event: "stop" });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Happy (81% confidence)"));
});

test("counselor sees the cue clear when the Student has no face", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
    }));
  });
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  const requestId = sent[0].id;
  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: requestId, label: "neutral", confidence: 0.72,
      },
    }));
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "unavailable", id: requestId },
    }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (72% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("No cue is currently shared"));
  assert.ok(button(root, "Stop"), "the session stays active");
});

test("a late result without an active request is ignored", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "result", id: "other-request", label: "sad", confidence: 0.7 },
    }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sad (70% confidence)"));
});

test("a result with the wrong id or below threshold is ignored", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
    }));
  });
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  const requestId = sent[0].id;

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: "some-other-id", label: "sad", confidence: 0.9,
      },
    }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sad (90% confidence)"));

  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: requestId, label: "sad", confidence: 0.2,
      },
    }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sad (20% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("No cue is currently shared"));
});

test("stop during an in-flight scan prevents a late result", async () => {
  const sent = [];
  let releaseScan;
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: () => new Promise(resolve => { releaseScan = resolve; }),
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-late" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await act(async () => { button(root, "Stop sharing").props.onClick(); });
  await act(async () => { releaseScan({ label: "neutral", confidence: 0.9 }); });
  await flush();

  assert.deepEqual(sent.map(item => item.event), ["consent", "stop"]);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (90% confidence)"));
});

test("unmount aborts an in-flight scan", async () => {
  let signal;
  let releaseScan;
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: (_video, options) => {
        signal = options.signal;
        return new Promise(resolve => { releaseScan = resolve; });
      },
      sendExpression: () => true,
      expressionEvent: { type: "expression", event: "request", id: "req-unmount" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  assert.ok(signal);
  await act(async () => { root.unmount(); });
  assert.equal(signal.aborted, true);
  await act(async () => { releaseScan({ label: "neutral", confidence: 0.9 }); });
});

test("stop from either side clears both local views", async () => {
  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
    }));
  });
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  const requestId = sent[0].id;
  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: {
        type: "expression", event: "result", id: requestId, label: "sad", confidence: 0.7,
      },
    }));
  });
  assert.ok(JSON.stringify(root.toJSON()).includes("Sad (70% confidence)"));
  await act(async () => {
    root.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "stop" },
    }));
  });
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sad (70% confidence)"));
  assert.ok(JSON.stringify(root.toJSON()).includes("The live expression cue was stopped"));
});

test("unknown role renders no expression UI", async () => {
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "GUIDANCE_STAFF",
    }));
  });
  assert.equal(root.toJSON(), null);
});

test("a failed request send shows feedback and sends nothing else", async () => {
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      role: "COUNSELOR",
      sendExpression: () => false,
    }));
  });
  await act(async () => { button(root, "Start live expression cue").props.onClick(); });
  assert.equal(button(root, "Stop"), undefined);
  assert.ok(JSON.stringify(root.toJSON()).includes("call is unavailable"));
});

test("a failed result send does not claim the cue was shared", async () => {
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: async () => ({ label: "happy", confidence: 0.8 }),
      sendExpression: payload => payload.event !== "result",
      expressionEvent: { type: "expression", event: "request", id: "req-send" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();
  assert.ok(!JSON.stringify(root.toJSON()).includes("Live cue shared with the Counselor"));
  assert.ok(JSON.stringify(root.toJSON()).includes("No cue was shared"));
});

test("phase change and tab hiding abort the active scan", async t => {
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  const listeners = {};
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (type, listener) => { listeners[type] = listener; },
    removeEventListener: (type, listener) => {
      if (listeners[type] === listener) delete listeners[type];
    },
  };
  t.after(() => {
    if (previousDocument) Object.defineProperty(globalThis, "document", previousDocument);
    else delete globalThis.document;
  });

  let signal;
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: (_video, options) => {
        signal = options.signal;
        return new Promise(() => {});
      },
      sendExpression: () => true,
      expressionEvent: { type: "expression", event: "request", id: "req-hide" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  assert.ok(signal);
  assert.equal(typeof listeners.visibilitychange, "function");

  document.visibilityState = "hidden";
  await act(async () => { listeners.visibilitychange(); });
  assert.equal(signal.aborted, true);
  assert.ok(!JSON.stringify(root.toJSON()).includes("Sharing a live expression cue"));

  let phaseRoot;
  let phaseSignal;
  await act(async () => {
    phaseRoot = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: (_video, options) => {
        phaseSignal = options.signal;
        return new Promise(() => {});
      },
      sendExpression: () => true,
      expressionEvent: { type: "expression", event: "request", id: "req-end" },
    }));
  });
  await act(async () => { button(phaseRoot, "Allow for this session").props.onClick(); });
  await act(async () => {
    phaseRoot.update(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      phase: "ended",
      scan: (_video, options) => {
        phaseSignal = options.signal;
        return new Promise(() => {});
      },
      sendExpression: () => true,
    }));
  });
  assert.equal(phaseSignal.aborted, true);
});

test("tab hiding after a result clears the shared cue", async t => {
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  const listeners = {};
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (type, listener) => { listeners[type] = listener; },
    removeEventListener: (type, listener) => {
      if (listeners[type] === listener) delete listeners[type];
    },
  };
  t.after(() => {
    if (previousDocument) Object.defineProperty(globalThis, "document", previousDocument);
    else delete globalThis.document;
  });

  const sent = [];
  let root;
  await act(async () => {
    root = create(React.createElement(ExpressionCuePanel, {
      ...panelProps,
      scan: async () => ({ label: "neutral", confidence: 0.8 }),
      sendExpression: payload => sent.push(payload),
      expressionEvent: { type: "expression", event: "request", id: "req-hide-result" },
    }));
  });
  await act(async () => { button(root, "Allow for this session").props.onClick(); });
  await flush();
  assert.ok(JSON.stringify(root.toJSON()).includes("Live cue shared with the Counselor"));
  assert.ok(!JSON.stringify(root.toJSON()).includes("Neutral (80% confidence)"));
  assert.ok(button(root, "Stop sharing"));

  document.visibilityState = "hidden";
  await act(async () => { listeners.visibilitychange(); });

  assert.equal(button(root, "Stop sharing"), undefined);
  assert.ok(JSON.stringify(root.toJSON()).includes("The live expression cue was stopped"));
  assert.deepEqual(sent.at(-1), { event: "stop" });
});
