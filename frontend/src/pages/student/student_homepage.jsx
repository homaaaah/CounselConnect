import { useState } from "react";
import { useAppointments } from "../../features/appointments";
import BookingModal from "../../components/appointments/BookingModal.jsx";

/**
 * Student homepage component extracted from HomePage.jsx.
 */
function StudentBookingModal({ onClose, user }) {
  const state = useAppointments(user.role_code);
  return <BookingModal open={true} onClose={onClose} state={state} />;
}

export default function StudentHomePage({ user }) {
  const canBook = user?.role_code === "STUDENT" || user?.role_code === "COUNSELOR";
  const active = canBook && user?.account_status === "ACTIVE";
  const student = user?.role_code === "STUDENT";
  const [bookingOpen, setBookingOpen] = useState(false);
  const canOpenModal = student && active;

  return (
    <main className="home-page bg-tint min-h-screen">
      {/* Hero */}
      <section className="homescreen-hero">
        <h1>In mood for talk{user?.first_name ? `, ${user.first_name}` : ""}?</h1>
        <p className="homescreen-subtitle">Connect with a counselor or reach out for immediate assistance.</p>

        <div className="action-buttons">
          {active ? (
            <button type="button" className="btn-action-schedule" onClick={() => setBookingOpen(true)}>
              <i className="fa-solid fa-calendar"></i> Schedule
            </button>
          ) : canBook ? (
            <span className="btn-action-schedule btn-action-disabled">
              <i className="fa-solid fa-hourglass-half"></i> Verification {user?.account_status === "PENDING_VERIFICATION" ? "pending" : "needed"}
            </span>
          ) : (
            <a href="#login" className="btn-action-schedule">
              <i className="fa-solid fa-calendar"></i> Schedule
            </a>
          )}
          <button type="button" className="btn-action-emergency">
            <i className="fa-solid fa-phone"></i> Emergency
          </button>
        </div>
      </section>

      {/* Student booking modal — calendar, slot details, request */}
      {canOpenModal && bookingOpen && (
        <StudentBookingModal onClose={() => setBookingOpen(false)} user={user} />
      )}
    </main>
  );
}
