import StudentAppointmentsPage from "./student/StudentAppointmentsPage";
import CounselorAppointmentsPage from "./counselor/CounselorAppointmentsPage";

/**
 * Compatibility wrapper for AppointmentsPage.
 * Delegates to StudentAppointmentsPage or CounselorAppointmentsPage based on user role.
 */
export default function AppointmentsPage({ user }) {
  if (user?.role_code === "COUNSELOR") return <CounselorAppointmentsPage user={user} />;
  return <StudentAppointmentsPage user={user} />;
}
