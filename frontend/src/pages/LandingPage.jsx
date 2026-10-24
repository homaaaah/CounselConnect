import { useEffect, useState } from "react";
import { usePublicContent } from "../features/content";
import appointmentImg from "../assets/appointment.jpg";
import counselorImg from "../assets/counselor.jpg";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";
import "./LandingPage.css";

/**
 * Public landing page matching design reference.
 */
export default function LandingPage({ onSignedIn }) {
  const { cmsBlocks, faqs, announcements, contacts, loading } = usePublicContent();
  const [modal, setModal] = useState(null);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const hero = cmsBlocks.find((b) => b.content_key === "landing_hero");

  useEffect(() => {
    if (!modal) return;
    const onKey = (e) => {
      if (e.key === "Escape") setModal(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modal]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  useEffect(() => {
    const onScroll = () => {
      const features =
        typeof document !== "undefined" ? document.getElementById("features") : null;
      const heroBottom = features?.offsetTop ?? 600;
      setShowBackToTop(window.scrollY > heroBottom);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const openLogin = (audience) => setModal({ kind: "login", audience });

  const navSections = [
    { id: "features", label: "Features" },
    { id: "news", label: "News" },
    { id: "faq", label: "FAQ" },
  ];

  return (
    <div className="landing-page" id="landing">
      {/* Top Header Bar */}
      <header className="landing-top-bar">
        <div className="container nav-container">
          <a href="#landing" className="logo">
            <span className="logo-badge">
              <i className="fa-solid fa-hands-holding-child"></i>
            </span>
            CounselConnect
          </a>
          <nav className="landing-nav-links" aria-label="Landing sections">
            {navSections.map((section) => (
              <a key={section.id} href={"#" + section.id}>{section.label}</a>
            ))}
          </nav>
          <div className="landing-header-actions">
            <button type="button" className="btn-top-login" onClick={() => openLogin("student")}>
              LOG IN
            </button>
            <button type="button" className="landing-nav-toggle" aria-expanded={mobileNavOpen}
              aria-controls="landing-mobile-nav" aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
              onClick={() => setMobileNavOpen(!mobileNavOpen)}>
              <i className={mobileNavOpen ? "fa-solid fa-xmark" : "fa-solid fa-bars"} aria-hidden="true"></i>
            </button>
          </div>
        </div>
        <div id="landing-mobile-nav" className={mobileNavOpen ? "open" : undefined} hidden={!mobileNavOpen}>
          <a href="#landing" onClick={() => setMobileNavOpen(false)}>Home</a>
          {navSections.map((section) => (
            <a key={section.id} href={"#" + section.id} onClick={() => setMobileNavOpen(false)}>{section.label}</a>
          ))}
          <button type="button" className="btn-top-login"
            onClick={() => { setMobileNavOpen(false); openLogin("student"); }}>
            LOG IN
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero">
        <div className="container hero-grid">
          <div className="hero-content">
            <h1>
              <i>Gentle Support</i> for<br />
              whatever today brings you.
            </h1>
            <p>
              {hero?.body ??
                "Request a guidance appointment, connect through scheduled text chat, and browse information published by the Counseling Office."}
            </p>
            <div className="hero-buttons">
              <button
                type="button"
                className="btn-get-started"
                onClick={() => setModal({ kind: "register", audience: "student" })}
              >
                Get Started
              </button>
            </div>
          </div>
          <div className="hero-image-wrapper">
            <img
              src={appointmentImg}
              alt="Counseling session placeholder"
              className="hero-placeholder-img"
            />
          </div>
        </div>
      </section>

      {/* Our Counselors Section */}
      <section className="counselors-section" id="counselors">
        <div className="container">
          <div className="counselors-header">
            <div>
              <h2>Our Counselors</h2>
              <p>Find available guidance appointments and review the details before submitting your request.</p>
            </div>
          </div>

          <div className="counselors-grid">
            <div className="counselor-image-card">
              <img
                className="counselor-photo"
                src={counselorImg}
                alt="Illustration representing campus guidance counseling"
              />
            </div>
            <div className="counselor-info-card">
              <h2>Meet with a Guidance Counselor</h2>
              <p>
                Students can review available appointment times, session mode, and counselor details before sending a request.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Feature Section */}
      <section className="feature-section" id="features">
        <div className="container">
          <div className="feature-section-header">
            <span className="feature-tag">Features</span>
            <h2>
              Everything you need to navigate your journey—<br />
              from direct support to self-guided resources.
            </h2>
          </div>

          <div className="feature-cards-grid">
            <div className="feature-card">
              <div className="feature-card-icon">
                <i className="fa-solid fa-comments"></i>
              </div>
              <div className="feature-card-title">Scheduled Text Chat</div>
              <div className="feature-card-desc">
                Continue appointment conversations through the scheduled messaging feature.
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon">
                <i className="fa-solid fa-calendar-days"></i>
              </div>
              <div className="feature-card-title">Seamless Scheduling</div>
              <div className="feature-card-desc">
                Book your counseling sessions with ease and find a time that works for you.
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon">
                <i className="fa-solid fa-brain"></i>
              </div>
              <div className="feature-card-title">Guidance Information</div>
              <div className="feature-card-desc">
                Browse FAQs and announcements published by the Counseling Office.
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon">
                <i className="fa-solid fa-mobile-screen"></i>
              </div>
              <div className="feature-card-title">Access Across Devices</div>
              <div className="feature-card-desc">
                Use CounselConnect on desktop and mobile browsers.
              </div>
            </div>
          </div>

          <div className="feature-cta-container">
            <h3>Convinced enough?</h3>
            <button
              type="button"
              className="btn-join-now"
              onClick={() => setModal({ kind: "register", audience: "student" })}
            >
              Join us now
            </button>
          </div>
        </div>
      </section>

      {/* Blog / Announcements Section */}
      <section className="blog-section" id="news">
        <div className="container">
          <div className="section-title-center">
            <span className="section-tag">FROM OUR BLOG</span>
            <h2>
              Guidance, growth, and campus well-being —<br />
              the latest news from your Counseling Office.
            </h2>
          </div>

          <div className="blog-grid">
            {loading ? (
              <p className="blog-empty">Loading announcements…</p>
            ) : announcements.length === 0 ? (
              <p className="blog-empty">No announcements yet.</p>
            ) : (
              announcements.map((a) => (
                <div className="blog-card" key={a.content_id}>
                  <div className="blog-img"><i className="fa-regular fa-image"></i></div>
                  <div className="blog-content">
                    <div className="blog-category">Announcement</div>
                    <div className="blog-title">{a.title}</div>
                    <div className="blog-snippet">{a.body}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="faq-section" id="faq">
        <div className="container">
          <div className="section-title-center">
            <h2 className="faq-heading">Frequently Asked Questions</h2>
          </div>
          {loading ? (
            <p className="blog-empty">Loading FAQs…</p>
          ) : faqs.length === 0 ? (
            <p className="blog-empty">No FAQs published yet.</p>
          ) : (
            <div className="faq-grid">
              {faqs.map((f) => (
                <details className="faq-item" name="faq" key={f.content_id}>
                  <summary>
                    <span>{f.title}</span>
                    <i className="fa-solid fa-chevron-down" aria-hidden="true"></i>
                  </summary>
                  <p>{f.body}</p>
                </details>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer>
        <div className="container">
          <div className="footer-grid">
            <div className="footer-col">
              <h3>Emergency support contacts</h3>
              {contacts.length === 0 ? (
                <p>Contact details are not currently published.</p>
              ) : contacts.map((contact) => (
                <p key={contact.contact_id}>
                  {contact.name}: {contact.contact_number}
                  {contact.description ? ` — ${contact.description}` : ""}
                </p>
              ))}
            </div>
            <div className="footer-col">
              <h3>Location</h3>
              <p>University of Caloocan City</p>
              <p>Contact the Counseling Office for location details.</p>
            </div>
          </div>

          <div className="footer-bottom">
            <div>&copy; {new Date().getFullYear()} CounselConnect</div>
            <a href="#landing" className={showBackToTop ? "back-to-top show" : "back-to-top"}>
              <i className="fa-solid fa-arrow-up"></i>
            </a>
          </div>
        </div>
      </footer>

      {/* Auth modal overlay (LOG IN / CONNECT WITH US) */}
      {modal && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          onClick={(e) => {
            if (e.target === e.currentTarget) setModal(null);
          }}
        >
          {modal.kind === "login" ? (
            <LoginPage
              key={modal.audience}
              inModal
              audience={modal.audience}
              onSignedIn={onSignedIn}
              onClose={() => setModal(null)}
              onSwitchAudience={() => openLogin(modal.audience === "student" ? "staff" : "student")}
              onSwitchToRegister={() => setModal({ kind: "register", audience: "student" })}
            />
          ) : (
            <RegisterPage
              inModal
              onClose={() => setModal(null)}
              onSwitchToLogin={() => openLogin("student")}
            />
          )}
        </div>
      )}
    </div>
  );
}
