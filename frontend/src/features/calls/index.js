/**
 * Feature module: appointment video calls (authenticated signaling, P2P media).
 */
export { useAppointmentCall } from "./useAppointmentCall";
export {
  CALL_PHASES,
  callStatusText,
  endReasonText,
  isWebRtcSupported,
  mediaErrorMessage,
  parseServerEvent,
} from "./signaling";
