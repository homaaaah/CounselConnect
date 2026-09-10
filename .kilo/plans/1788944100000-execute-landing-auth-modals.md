# Execute — Landing auth modals (login/register overlay)

**Risk class:** MEDIUM (UI integration; auth logic reused unchanged from tested components)
**Parent design:** verified against on-disk code on 2026-09-10 (line-accurate).

## Context

The React port (3 phases) serves the Capstone landing at `/`. LOG IN and CONNECT WITH US currently navigate to the full-page `#login`/`#register` hash pages. The original Capstone UX opened login/signup as modals — this plan restores that UX by rendering the **existing tested** `LoginPage`/`RegisterPage` inside an overlay on the landing. No new auth code, no endpoints, no duplication.

Hard constraints (verified):
- `frontend/tests/session.test.cjs` asserts full-page LoginPage markup: `findByProps({ href: "#staff-login" })`, `htmlFor="identifier"`, `id="identifier"` (`type="email"` for staff), audience `h1` text, form `onSubmit` + 700 ms redirect. Default (non-modal) rendering MUST stay identical.
- Tests never mount `LandingPage`/`RegisterPage` (grep-verified) — free to add modal props.
- `App.tsx:62` renders `<LandingPage />`; session accept is `session.accept` (App.tsx:47).
- LoginPage already redirects by role after success (its `useEffect` sets hash `#review`/`#home`/`#landing` after 700 ms) — reuse as-is; hash change unmounts the landing incl. modal.

## Steps

1. Write ACTIVE `.ai/CURRENT_TASK.md` (objective/route/scope/criteria as in this plan).

2. Edit `frontend/src/pages/LoginPage.tsx`:
   - Signature: add optional `inModal = false`, `onClose`, `onSwitchAudience`, `onSwitchToRegister` (all no-ops when absent).
   - Keep ALL state/handlers/effect/labels/inputs EXACTLY as-is (test contracts).
   - Extract the existing card content into the JSX as-is; wrap: `inModal ? <div className="modal-card">{body}</div> : <main className="auth-shell"><div className="modal-card">{body}</div></main>`.
   - When `inModal`, render inside the card, before the header:
     `<button type="button" className="modal-close" onClick={onClose} aria-label="Close"><i className="fa-solid fa-xmark"></i></button>`
   - Cross-links: when `inModal`, replace the three `<p className="signup-text">`/footer-link anchors with in-modal buttons:
     - audience switch: `<button type="button" className="linklike" onClick={onSwitchAudience}>{isStudent ? "Counselor / Staff sign in" : "Student sign in"}</button>`
     - to register: `<button type="button" className="linklike" onClick={onSwitchToRegister}>Register</button>`
     - drop the "Back to landing page" footer link (modal already sits on the landing).
     When `!inModal` keep the current anchors byte-for-byte (tests).

3. Edit `frontend/src/pages/RegisterPage.tsx` (same pattern):
   - Signature: add optional `inModal = false`, `onClose`, `onSwitchToLogin`.
   - All form logic unchanged; wrap as above (signup-card).
   - When `inModal`: add the same close button; replace the footer "Back to landing page" link with:
     `<p className="signup-text">Already have an account? <button type="button" className="linklike" onClick={onSwitchToLogin}>Sign in</button></p>`
   - When `!inModal`: current markup unchanged.

4. Edit `frontend/src/pages/LandingPage.tsx`:
   - Imports: add `useEffect, useState` (react), `LoginPage`, `RegisterPage`, `type AuthResult` (../features/auth).
   - Props: `{ onSignedIn }: { onSignedIn: (auth: AuthResult) => void }`.
   - State: `const [modal, setModal] = useState<null | { kind: "login" | "register"; audience: "student" | "staff" }>(null);`
   - Escape handler (only while modal open): keydown → Escape → setModal(null); cleanup on unmount/change.
   - `openLogin = (audience) => setModal({ kind: "login", audience })`.
   - Header LOG IN anchor → `<button type="button" className="btn-login" onClick={() => openLogin("student")}>LOG IN</button>`.
   - Hero CONNECT WITH US anchor → `<button type="button" className="btn-connect" onClick={() => setModal({ kind: "register" })}>CONNECT WITH US <i …chevron… /></button>`.
   - Overlay before the closing wrapper `</div>`:
     ```tsx
     {modal && (
       <div className="modal-overlay" role="dialog" aria-modal="true"
         onClick={(e) => { if (e.target === e.currentTarget) setModal(null); }}>
         {modal.kind === "login" ? (
           <LoginPage key={modal.audience} inModal audience={modal.audience}
             onSignedIn={onSignedIn} onClose={() => setModal(null)}
             onSwitchAudience={() => openLogin(modal.audience === "student" ? "staff" : "student")}
             onSwitchToRegister={() => setModal({ kind: "register" })} />
         ) : (
           <RegisterPage inModal onClose={() => setModal(null)}
             onSwitchToLogin={() => openLogin("student")} />
         )}
       </div>
     )}
     ```
   - `key={modal.audience}` resets the login form when flipping audience.

5. Edit `frontend/src/App.tsx` line 62: `<LandingPage />` → `<LandingPage onSignedIn={session.accept} />`.

6. Append to `frontend/src/index.css` (global class rules only, no element selectors):
   ```css
   /* Auth modal overlay (landing LOG IN / CONNECT WITH US) */
   .modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5);
     display: flex; align-items: center; justify-content: center; padding: 1.5rem; z-index: 50; }
   .modal-overlay .modal-card, .modal-overlay .signup-card { max-height: 85vh; overflow-y: auto; }
   .modal-close { position: absolute; top: 14px; right: 14px; background: transparent; border: none;
     color: var(--text-muted); font-size: 1.1rem; cursor: pointer; padding: 4px; transition: color 0.2s; }
   .modal-close:hover { color: var(--text-dark); }
   .linklike { background: transparent; border: none; padding: 0; font: inherit; color: #2563eb;
     font-weight: 600; text-decoration: none; cursor: pointer; }
   .linklike:hover { text-decoration: underline; }
   ```

7. Verification:
   - `npm run build` (tsc + vite; 51 modules expected).
   - `npm test` — 16/16 (full-page auth rendering unchanged).
   - Dev server: `/` landing renders; `/src/pages/LandingPage.tsx` serves; static grep of served module shows `modal-overlay` wiring.
   - Note honestly: modal open/close/switch interactions are client-side state — verified by build + tests + user's browser check.

8. Update `CHANGELOG.md` (new session entry: landing auth modals; LOG IN/CONNECT WITH US now open overlays; full-page routes unchanged) and finalize `.ai/CURRENT_TASK.md` as COMPLETED with actual verification results.

## Acceptance criteria

- LOG IN opens the student login modal; in-modal audience switch and Register switch work; CONNECT WITH US opens the register modal; X / overlay click / Escape close; register success shows `next_step` in-modal; login success redirects by role as before.
- Full-page `#login`/`#staff-login`/`#register` render unchanged; build green; tests 16/16.

## Out of scope

Hash-route auth pages, backend, session logic, docs contracts.
