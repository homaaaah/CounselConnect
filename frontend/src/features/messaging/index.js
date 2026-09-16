/**
 * Feature module: messaging (live chat UI).
 * Appointment-derived scheduled chat; no general messaging inbox.
 */
export { default as ScheduledSessionLauncher } from "./ScheduledSessionLauncher";
export { useAppointmentChat } from "./useAppointmentChat";
export { useScheduledSessions, socketUrl } from "./useScheduledSessions";
