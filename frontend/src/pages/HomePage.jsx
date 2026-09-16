import StudentHomePage from "./student/student_homepage";
import CounselorDashboard from "./counselor/counselor_dashboard";

/**
 * Compatibility wrapper for HomePage.
 * Delegates to StudentHomePage or CounselorDashboard based on user role.
 */
export default function HomePage({ user }) {
  if (user?.role_code === "COUNSELOR") return <CounselorDashboard user={user} />;
  return <StudentHomePage user={user} />;
}
