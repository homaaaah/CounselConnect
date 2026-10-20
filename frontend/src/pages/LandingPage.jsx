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
  const { cmsBlocks, faqs, announcements, loading } = usePublicContent();
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
                "Appoint your next session in just a few clicks, talk with a compassionate professional, and explore wellness guidance at your pace."}
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
              <p>Professional and qualified therapists who you can trust</p>
            </div>
            <div className="counselors-nav">
              <button type="button" className="counselor-nav-btn" aria-label="Previous counselor">
                &lt;
              </button>
              <button type="button" className="counselor-nav-btn" aria-label="Next counselor">
                &gt;
              </button>
            </div>
          </div>

          <div className="counselors-grid">
            <div className="counselor-image-card">
              <img
                className="counselor-photo"
                src={counselorImg}
                alt="Portrait of the university guidance counselor"
              />
            </div>
            <div className="counselor-info-card">
              <h2>Mr. Firstname Lastname</h2>
              <p>
                This is the space to introduce visitors to the business or brand. Briefly explain who's behind it, what it does, and what makes it unique. Share its core values and what this site has to offer.
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
                <i className="fa-solid fa-video"></i>
              </div>
              <div className="feature-card-title">Live Communication</div>
              <div className="feature-card-desc">
                Enjoy interactive talks with chat and video supported conversations.
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
              <div className="feature-card-title">AI Assisted Counseling</div>
              <div className="feature-card-desc">
                Get intelligent support and personalized guidance throughout your counseling journey.
              </div>
            </div>

            <div className="feature-card">
              <div className="feature-card-icon">
                <i className="fa-solid fa-mobile-screen"></i>
              </div>
              <div className="feature-card-title">Accessible Session Everywhere</div>
              <div className="feature-card-desc">
                Stay connected to counseling support through a responsive experience built for desktop and mobile.
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
                <div className="faq-card" key={f.content_id}>
                  <h3>{f.title}</h3>
                  <p>{f.body}</p>
                </div>
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
              <h3>Contact</h3>
              <p>info@mysite.com</p>
              <p>123-456-7890</p>
            </div>
            <div className="footer-col">
              <h3>Location</h3>
              <p>500 Terry Francois Street,</p>
              <p>San Francisco, CA 94158</p>
            </div>
            <div className="footer-col">
              <h3>Follow</h3>
              <div className="social-icons">
                <a href="#" className="social-icon"><i className="fa-brands fa-linkedin-in"></i></a>
                <a href="#" className="social-icon"><i className="fa-brands fa-youtube"></i></a>
                <a href="#" className="social-icon"><i className="fa-brands fa-instagram"></i></a>
                <a href="#" className="social-icon"><i className="fa-brands fa-facebook-f"></i></a>
              </div>
            </div>
          </div>

          <div className="footer-bottom">
            <div>&copy; 2035 by CounselConnect</div>
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
