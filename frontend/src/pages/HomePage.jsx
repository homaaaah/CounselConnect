import { useRef } from "react";
import { usePublicContent } from "../features/content";
import { useAppointments, formatSchedule } from "../features/appointments";

/**
 * Homepage after sign-in (DFD Master System Flow "Student services") —
 * homescreen design ported into React and wired to real data: upcoming
 * appointments from /appointments, emergency contacts from
 * /content/emergency-contacts. The static mock (fake counselor, hardcoded
 * calendar, alert-based booking) is retired.
 */
export default function HomePage({ user }) {
  const { announcements, contacts } = usePublicContent();
  const appointments = useAppointments(user?.role_code ?? "");
  const contactsRef = useRef(null);

  const canBook = user?.role_code === "STUDENT" || user?.role_code === "COUNSELOR";
  const active = canBook && user?.account_status === "ACTIVE";

  const upcoming = appointments.appointments.items
    .filter((a) => a.status === "PENDING" || a.status === "CONFIRMED")
    .filter((a) => new Date(a.ends_at).getTime() > Date.now())
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at))
    .slice(0, 3);

  const scrollToContacts = () => {
    contactsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <main className="home-page">
      {/* Hero */}
      <section className="homescreen-hero">
        <div className="support-badge">
          <i className="fa-solid fa-circle-info"></i> Confidential student support services
        </div>

        <h1>Your mental well-being matters to us.</h1>

        <p>
          Connect with professional university counselors in a safe, private space.
          Whether you're feeling overwhelmed or just need to talk, we're here to help
          you navigate your academic journey.
        </p>

        <div className="action-buttons">
          {active ? (
            <a href="#appointments" className="btn-action-schedule">
              <i className="fa-solid fa-calendar"></i> Schedule
            </a>
          ) : canBook ? (
            <span className="btn-action-schedule btn-action-disabled">
              <i className="fa-solid fa-hourglass-half"></i> Verification {user?.account_status === "PENDING_VERIFICATION" ? "pending" : "needed"}
            </span>
          ) : (
            <a href="#login" className="btn-action-schedule">
              <i className="fa-solid fa-calendar"></i> Schedule
            </a>
          )}
          <button type="button" className="btn-action-emergency" onClick={scrollToContacts}>
            <i className="fa-solid fa-phone"></i> Emergency
          </button>
        </div>

        <div className="features-footer-row">
          <div className="feature-item">
            <i className="fa-solid fa-shield"></i> Fully Private
          </div>
          <div className="feature-item">
            <i className="fa-solid fa-clock"></i> 24/7 Support
          </div>
          <div className="feature-item">
            <i className="fa-solid fa-video"></i> Video/In-person
          </div>
        </div>
      </section>

      {/* Upcoming appointments (real data, authorized users only) */}
      {active && (
        <section className="home-appointments-section">
          <div className="home-section-inner">
            <h2>Your upcoming appointments</h2>
            {appointments.error && <p className="home-empty" role="alert">{appointments.error}</p>}
            {upcoming.length === 0 && !appointments.error && (
              <p className="home-empty">No upcoming appointments yet. Use Schedule to request one.</p>
            )}
            {upcoming.length > 0 && (
              <ul className="home-appointment-list">
                {upcoming.map((a) => (
                  <li key={a.appointment_id} className="home-appointment-card">
                    <div className="home-appointment-when">
                      <i className="fa-regular fa-calendar"></i>
                      <div>
                        <p className="home-appointment-date">{formatSchedule(a.starts_at)}</p>
                        <p className="home-appointment-meta">Until {formatSchedule(a.ends_at)}</p>
                      </div>
                    </div>
                    <div className="home-appointment-details">
                      <p>{user?.role_code === "COUNSELOR" ? `Student: ${a.student_name}` : `Counselor: ${a.counselor_name}`}</p>
                      <p>{a.campus_name} · {a.appointment_mode === "ONLINE" ? "Online" : "Face-to-face"}</p>
                    </div>
                    <span className={"home-status-badge " + (a.status === "CONFIRMED" ? "confirmed" : "pending")}>
                      {a.status === "CONFIRMED" ? "Confirmed" : "Awaiting review"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <a href="#appointments" className="home-manage-link">Manage appointments</a>
          </div>
        </section>
      )}

      {/* Announcements */}
      <section className="home-announcements-section">
        <div className="home-section-inner">
          <h2>Announcements</h2>
          {announcements.length === 0 ? (
            <p className="home-empty">No announcements yet.</p>
          ) : (
            <ul className="home-announcement-list">
              {announcements.map((a) => (
                <li key={a.content_id} className="home-announcement-item">
                  <p className="home-announcement-title">{a.title}</p>
                  <p>{a.body}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* Emergency contacts (real, seeded; Emergency scrolls here) */}
      <section className="home-contacts-section" ref={contactsRef}>
        <div className="home-section-inner">
          <h2><i className="fa-solid fa-phone"></i> Emergency contacts</h2>
          {contacts.length === 0 ? (
            <p className="home-empty">No contacts configured yet.</p>
          ) : (
            <ul className="home-contact-list">
              {contacts.map((c) => (
                <li key={c.contact_id} className="home-contact-item">
                  <p className="home-contact-name">{c.name}</p>
                  <p className="home-contact-number">{c.contact_number}</p>
                  {c.description && <p className="home-contact-desc">{c.description}</p>}
                </li>
              ))}
            </ul>
          )}
          <p className="home-contact-note">
            In an immediate crisis, contact your local emergency services first.
          </p>
        </div>
      </section>
    </main>
  );
}
