import { useEffect, useState } from "react";
import { usePublicContent } from "../features/content";
import appointmentImg from "../assets/appointment.jpg";
import communicationImg from "../assets/communication.jpg";
import libraryImg from "../assets/library.jpg";
import counselorImg from "../assets/counselor.jpg";
import LoginPage from "./LoginPage";
import RegisterPage from "./RegisterPage";

/**
 * Public landing page (DFD Master System Flow entry) — Capstone design
 * ported into React. Published announcements and office CMS content from
 * content_items map into the marketing layout: the hero paragraph uses the
 * CMS landing_hero block (Capstone copy as fallback), announcements render
 * as blog cards, and FAQs render in a strip below.
 *
 * LOG IN / CONNECT WITH US open the existing auth pages as modal overlays
 * (LoginPage / RegisterPage in inModal mode) instead of navigating away;
 * the full-page #login / #staff-login / #register hash routes remain.
 */
export default function LandingPage({ onSignedIn }) {
  const { cmsBlocks, faqs, announcements, loading } = usePublicContent();
  const [modal, setModal] = useState(null);
  const [scrolled, setScrolled] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [activeSection, setActiveSection] = useState(null);
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
    // glass nav floats over the hero first; bg-tint bar kicks in after 60px.
    // back-to-top stays hidden while the hero is on screen.
    const onScroll = () => {
      setScrolled(window.scrollY > 60);
      const features =
        typeof document !== "undefined" ? document.getElementById("features") : null;
      const heroBottom = features?.offsetTop ?? 700;
      setShowBackToTop(window.scrollY > heroBottom);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    for (const id of ["features", "news", "faq"]) {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    }
    return () => observer.disconnect();
  }, [loading]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMobileNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mobileNavOpen]);

  const openLogin = (audience) => setModal({ kind: "login", audience });

  const navSections = [
    { id: "features", label: "Features" },
    { id: "news", label: "News" },
    { id: "faq", label: "FAQ" },
  ];

  return (
    <div className="landing-page" id="landing">
      {/* Header */}
      <header className={scrolled ? "scrolled" : undefined}>
        <div className="container nav-container">
          <a href="#landing" className="logo">CounselConnect</a>
          <ul className="nav-links">
            <li><a href="#landing" className="active">Home</a></li>
            {navSections.map((section) => (
              <li key={section.id}>
                <a href={"#" + section.id}
                  className={activeSection === section.id ? "active" : undefined}>{section.label}</a>
              </li>
            ))}
          </ul>
          <button type="button" className="btn-login" onClick={() => openLogin("student")}>LOG IN</button>
          <button type="button" className="nav-toggle" aria-expanded={mobileNavOpen}
            aria-controls="landing-mobile-nav" aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileNavOpen(!mobileNavOpen)}>
            <i className={mobileNavOpen ? "fa-solid fa-xmark" : "fa-solid fa-bars"} aria-hidden="true"></i>
          </button>
        </div>
        <div id="landing-mobile-nav" className={mobileNavOpen ? "open" : undefined} hidden={!mobileNavOpen}>
          <a href="#landing" onClick={() => setMobileNavOpen(false)}>Home</a>
          {navSections.map((section) => (
            <a key={section.id} href={"#" + section.id} onClick={() => setMobileNavOpen(false)}>{section.label}</a>
          ))}
          <button type="button" className="btn-login" onClick={() => { setMobileNavOpen(false); openLogin("student"); }}>LOG IN</button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero">
        <div className="container">
          <h1><i>Gentle Support</i> for whatever today brings you.</h1>
          <p>
            {hero?.body ??
              "Appoint your next session in just a few clicks, talk with a compassionate professional, and explore wellness guidance at your pace."}
          </p>
          <button type="button" className="btn-connect" onClick={() => setModal({ kind: "register", audience: "student" })}>
            CONNECT WITH US
            <i className="fa-solid fa-chevron-right" style={{ fontSize: "0.75rem" }} />
          </button>
        </div>
      </section>

      {/* Why Choose Us Section */}
      <section className="why-section" id="features">
        <div className="container">
          <div className="why-grid">
            <div className="why-left">
              <h2>WHY CHOOSE US?</h2>
            </div>
            <div className="why-cards">
              <div className="why-card">
                <img
                  className="why-card-img"
                  src={appointmentImg}
                  alt="Student booking a real-time appointment"
                />
                <p className="why-card-desc">
                  {/* TODO: replace dummy copy with real feature descriptions */}
                  Reserve and manage your guidance sessions in real time —
                  pick an open slot, confirm instantly, and get reminders
                  before your schedule.
                </p>
                <div className="why-card-title">Real-time Appointments</div>
              </div>
              <div className="why-card">
                <img
                  className="why-card-img"
                  src={communicationImg}
                  alt="Live chat communication with a counselor"
                />
                <p className="why-card-desc">
                  {/* TODO: replace dummy copy with real feature descriptions */}
                  Reach your counselor through secure live messaging whenever
                  you need someone to listen.
                </p>
                <div className="why-card-title">Live Communication</div>
              </div>
              <div className="why-card">
                <img
                  className="why-card-img"
                  src={libraryImg}
                  alt="Curated wellness library resources"
                />
                <p className="why-card-desc">
                  {/* TODO: replace dummy copy with real feature descriptions */}
                  Explore curated wellness articles and resources recommended
                  for your personal journey.
                </p>
                <div className="why-card-title">Curated Wellness Library</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Bio Section */}
      <section className="bio-section">
        <div className="container">
          <div className="bio-grid">
            <img
              className="bio-image-placeholder"
              src={counselorImg}
              alt="Portrait of the university guidance counselor"
            />
            <div className="bio-card">
              <h2>Ms. Firstname A. Lastname</h2>
              <p>
                This is the space to introduce the university's guidance
                counselors — who they are, how they support students, and what
                makes the Guidance and Counseling Office unique. Real counselor
                profiles arrive with the CMS content team.
              </p>
            </div>
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
          <p className="dev-review-link">
            <a href="#review">Counselor review console (dev)</a>
          </p>
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
