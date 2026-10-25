/**
 * Pure helpers for the appointment call UI.
 *
 * Signaling is relayed by the backend; this module only validates/parses the
 * browser-side wire shape and maps device failures to safe messages. Media,
 * SDP, and candidates are never persisted.
 */

export const CALL_PHASES = [
  "idle",
  "joining",
  "waiting",
  "negotiating",
  "connected",
  "ended",
  "failed",
];

export const isWebRtcSupported = () =>
  typeof RTCPeerConnection === "function"
  && typeof navigator !== "undefined"
  && typeof navigator?.mediaDevices?.getUserMedia === "function";

export function parseServerEvent(raw) {
  try {
    const event = JSON.parse(raw);
    if (!event || typeof event !== "object" || typeof event.type !== "string") return null;
    return event;
  } catch {
    return null;
  }
}

export function callStatusText(phase, endReason = "") {
  switch (phase) {
    case "joining": return "Starting camera and microphone…";
    case "waiting": return "Waiting for the other participant…";
    case "negotiating": return "Connecting…";
    case "connected": return "Connected";
    case "failed": return "Call failed";
    case "ended": return endReasonText(endReason);
    default: return "Not in a call";
  }
}

export function endReasonText(reason) {
  switch (reason) {
    case "PEER_LEFT": return "The other participant left the call.";
    case "PEER_HUNG_UP": return "The other participant hung up.";
    case "REPLACED": return "This call was opened in another window.";
    case "CALL_UNAVAILABLE": return "The call window has ended or the appointment is no longer available.";
    case "SESSION_ENDED": return "Your session ended. Sign in again to continue.";
    case "YOU_HUNG_UP": return "You left the call.";
    default: return "The call ended.";
  }
}

export function mediaErrorMessage(error) {
  switch (error?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera and microphone access was blocked. Allow access in your browser settings, then try again.";
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "No camera or microphone was found on this device.";
    case "NotReadableError":
    case "TrackStartError":
      return "Your camera or microphone is already in use by another app. Close it and try again.";
    case "OverconstrainedError":
      return "This device cannot provide the requested camera or microphone.";
    default:
      return error instanceof Error && error.message
        ? error.message
        : "Could not start the video call. Try again.";
  }
}
