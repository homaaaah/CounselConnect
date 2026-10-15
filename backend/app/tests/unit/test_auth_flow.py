"""Focused tests for ADR-019 login/session/CSRF (auth service + endpoints).

Runs against the dedicated MySQL test schema (conftest) with a per-test
savepoint-rollback session. Endpoint tests use FastAPI TestClient with the
dependency session overridden onto the same rollback transaction so no
row ever leaks between tests.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.main import create_app
from app.modules.accounts.models import StudentProfile, User
from app.modules.auth.models import UserSession
from app.modules.auth.service import (
    ABSOLUTE_LIFETIME,
    IDLE_TIMEOUT,
    SESSION_COOKIE,
    AuthService,
    _as_utc,
)
from app.database import get_session

from ..conftest import db_session  # noqa: F401  (fixture import)


@pytest.fixture()
def student(db_session: Session) -> User:
    """A PENDING_VERIFICATION student with a known password + profile."""
    from sqlalchemy import text

    # The baseline test schema ships with empty lookup tables.
    db_session.execute(text("INSERT IGNORE INTO campuses (campus_name) VALUES ('Test Campus')"))
    db_session.execute(
        text(
            "INSERT IGNORE INTO departments (department_name) VALUES ('Test Dept')"
        )
    )
    db_session.execute(
        text(
            "INSERT INTO programs (department_id, program_code, program_name) "
            "SELECT department_id, 'TST', 'Test Program' FROM departments "
            "WHERE department_name = 'Test Dept' LIMIT 1"
        )
    )
    db_session.flush()
    campus_id = db_session.execute(text("SELECT campus_id FROM campuses LIMIT 1")).scalar()
    program_id = db_session.execute(text("SELECT program_id FROM programs LIMIT 1")).scalar()

    user = User(
        email="auth-student@example.edu",
        password_hash=hash_password("student-pass-1"),
        role_code="STUDENT",
        account_status="PENDING_VERIFICATION",
        first_name="Ana",
        last_name="Santos",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        StudentProfile(
            user_id=user.user_id,
            student_number="2026-AUTHTST",
            campus_id=campus_id,
            program_id=program_id,
            year_level=1,
            section="A",
        )
    )
    db_session.flush()
    return user


@pytest.fixture()
def counselor(db_session: Session) -> User:
    user = User(
        email="auth-counselor@example.edu",
        password_hash=hash_password("counselor-pass-1"),
        role_code="COUNSELOR",
        account_status="ACTIVE",
        first_name="Cora",
        last_name="Reyes",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def superadmin(db_session: Session) -> User:
    user = User(
        email="auth-super@example.edu",
        password_hash=hash_password("super-pass-1"),
        role_code="SUPERADMIN",
        account_status="ACTIVE",
        first_name="Super",
        last_name="Admin",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    """App wired to the rollback session (DB state never escapes a test)."""
    app = create_app(run_cleanup=False)

    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    return TestClient(app)


def _login(client: TestClient, identifier: str, password: str):
    return client.post(
        "/api/v1/auth/login", json={"identifier": identifier, "password": password}
    )


# --------------------------------------------------------------- service


def test_student_login_accepts_student_number_or_email(db_session, student):
    from app.core.exceptions import AppError

    svc = AuthService(db_session)
    by_number = svc.login("2026-AUTHTST", "student-pass-1")
    assert by_number[0].user_id == student.user_id
    # Pending Students may also sign in with their registration email
    # (ADR-029 bootstrap; #7 email-or-student-number login).
    by_email = svc.login("auth-student@example.edu", "student-pass-1")
    assert by_email[0].user_id == student.user_id
    # Same-error rule: unknown identifier and wrong password are identical.
    for bad in [("nope", "student-pass-1"), ("2026-AUTHTST", "wrong")]:
        with pytest.raises(AppError) as ei:
            svc.login(*bad)
        assert ei.value.code == "INVALID_CREDENTIALS"
        assert ei.value.status_code == 401


def test_login_allowed_statuses_and_denied(db_session, student):
    from app.core.exceptions import AppError

    svc = AuthService(db_session)
    # PENDING_VERIFICATION may log in (must reach COR re-verification).
    svc.login("2026-AUTHTST", "student-pass-1")
    # VERIFICATION_EXPIRED is still allowed (re-verification reachable).
    student.account_status = "VERIFICATION_EXPIRED"
    db_session.flush()
    svc.login("2026-AUTHTST", "student-pass-1")
    # Any non-allowed state is refused. The v1 enum has no other real
    # status, so the guard is proven on the module constant itself.
    from app.modules.auth import service as auth_service_mod

    allowed = {"PENDING_VERIFICATION", "ACTIVE", "VERIFICATION_EXPIRED"}
    assert set(auth_service_mod._LOGIN_ALLOWED_STATUSES) == allowed
    student.account_status = "PENDING_VERIFICATION"  # restore
    db_session.flush()


def test_bcrypt_hash_upgrades_to_argon2_on_login(db_session, student):
    import bcrypt as _bcrypt

    student.password_hash = _bcrypt.hashpw(
        b"student-pass-1", _bcrypt.gensalt()
    ).decode()
    db_session.flush()
    svc = AuthService(db_session)
    user, _session, _raw, _csrf = svc.login("2026-AUTHTST", "student-pass-1")
    assert user.password_hash.startswith("$argon2id")
    assert verify_password("student-pass-1", user.password_hash)


def test_login_revokes_previous_sessions(db_session, student):
    svc = AuthService(db_session)
    _, s1, _, _ = svc.login("2026-AUTHTST", "student-pass-1")
    _, s2, _, _ = svc.login("2026-AUTHTST", "student-pass-1")
    db_session.flush()
    db_session.expire_all()  # bulk revoke bypasses the identity map
    fresh1 = db_session.get(UserSession, s1.session_id)
    fresh2 = db_session.get(UserSession, s2.session_id)
    assert fresh1.revoked_at is not None
    assert fresh2.revoked_at is None


def test_existing_student_number_collision_cannot_block_counselor(client, db_session, student, counselor):
    profile = db_session.get(StudentProfile, student.user_id)
    profile.student_number = counselor.email
    db_session.flush()
    response = _login(client, counselor.email, "counselor-pass-1")
    assert response.status_code == 200
    assert response.json()["user"]["user_id"] == counselor.user_id
    assert _login(client, counselor.email, "student-pass-1").status_code == 401


def test_registration_rejects_staff_identifier_collision(db_session, counselor, academic_references):
    from app.core.exceptions import AppError
    from app.modules.accounts.schemas import StudentRegistrationRequest
    from app.modules.accounts.service import AccountsService

    payload = StudentRegistrationRequest(email="new-student@example.edu", password="student-pass-1",
        first_name="Ana", last_name="Santos", student_number=counselor.email,
        campus_id=academic_references[0], program_id=academic_references[1], year_level=1, section="A")
    service = AccountsService(db_session)
    with pytest.raises(AppError) as error:
        service.register_student(payload)
    assert error.value.code == "INVALID_STUDENT_NUMBER"
    assert service.repository.find_user_by_email(payload.email) is None


def test_csrf_recovery_after_reload_keeps_other_tab_token_valid(client, counselor):
    login = _login(client, counselor.email, "counselor-pass-1").json()
    recovered = client.get("/api/v1/auth/csrf")
    assert recovered.status_code == 200
    assert recovered.json()["csrf_token"] == login["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": login["csrf_token"]}).status_code == 204


# ---------------------------------------------------- endpoint flow (cookie+CSRF)


def test_login_sets_cookie_and_returns_csrf_and_expiries(client, student):
    r = _login(client, "2026-AUTHTST", "student-pass-1")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role_code"] == "STUDENT"
    assert body["csrf_token"]
    assert body["idle_expires_at"] and body["absolute_expires_at"]
    set_cookie = r.headers.get("set-cookie", "")
    # Cookie hygiene: HttpOnly, SameSite=Lax, scoped to /, 12h max-age.
    assert SESSION_COOKIE in set_cookie
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()
    assert "max-age=43200" in set_cookie.lower()


def test_me_requires_session_and_then_returns_user(client, student):
    assert client.get("/api/v1/auth/me").status_code == 401
    _login(client, "2026-AUTHTST", "student-pass-1")
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "auth-student@example.edu"


def test_unsafe_methods_require_csrf(client, student):
    _login(client, "2026-AUTHTST", "student-pass-1")
    r = client.post("/api/v1/auth/refresh")  # no X-CSRF-Token
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


def test_refresh_returns_session_metadata(client, student):
    login = _login(client, "2026-AUTHTST", "student-pass-1").json()
    r = client.post(
        "/api/v1/auth/refresh", headers={"X-CSRF-Token": login["csrf_token"]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["user_id"] == login["user"]["user_id"]
    assert body["csrf_token"] == login["csrf_token"]


def test_logout_revokes_session_and_clears_cookie(client, student):
    login = _login(client, "2026-AUTHTST", "student-pass-1").json()
    csrf = login["csrf_token"]
    r = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_role_gates_screening_endpoints(client, student, counselor):
    # Student session: the Counselor-only directory/screening lists are denied.
    _login(client, "2026-AUTHTST", "student-pass-1")
    for path in ("/api/v1/cor-screenings", "/api/v1/accounts/students"):
        r = client.get(path)
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "FORBIDDEN_ROLE"
    # Counselor session: allowed.
    _login(client, "auth-counselor@example.edu", "counselor-pass-1")
    for path in ("/api/v1/cor-screenings", "/api/v1/accounts/students"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "items" in r.json()


def test_csrf_required_on_unsafe_protected_actions(client, student):
    _login(client, "2026-AUTHTST", "student-pass-1")
    # No X-CSRF-Token header on POST confirm → 403, never the action.
    r = client.post("/api/v1/cor-screenings/confirm", json={})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CSRF_TOKEN_INVALID"


# ------------------------------------------------------------ expiry rules


def test_idle_expiry_kills_session(db_session, student):
    """Idle window is computed from last_activity_at (1h; genuine activity
    only). The timeline CHECK forbids writing activity before created_at,
    so expiry classification is tested with a simulated clock."""
    from datetime import datetime, timezone as tz

    svc = AuthService(db_session)
    _, session, raw, _csrf = svc.login("2026-AUTHTST", "student-pass-1")
    db_session.flush()

    later = datetime.now(tz.utc) + timedelta(minutes=30)
    expired = datetime.now(tz.utc) + IDLE_TIMEOUT + timedelta(minutes=1)
    assert svc._is_live(session, now=later) is True
    assert svc._is_live(session, now=expired) is False  # idle-expired = dead


def test_absolute_expiry_kills_session(db_session, student):
    """Absolute expiry (12h, never sliding) is computed from
    absolute_expires_at even when activity is recent."""
    from datetime import datetime, timezone as tz

    from app.core.exceptions import AppError

    svc = AuthService(db_session)
    _, session, raw, _ = svc.login("2026-AUTHTST", "student-pass-1")
    db_session.flush()

    # Clock past the absolute ceiling → dead regardless of fresh activity.
    past_ceiling = datetime.now(tz.utc) + ABSOLUTE_LIFETIME + timedelta(minutes=1)
    assert svc._is_live(session, now=past_ceiling) is False

    # End-to-end: DB row itself shifted past the ceiling (invariant kept —
    # only the clock moves, activity stays within its window).
    session.created_at = _as_utc(session.created_at) - ABSOLUTE_LIFETIME
    session.last_activity_at = _as_utc(session.last_activity_at) - ABSOLUTE_LIFETIME
    session.absolute_expires_at = _as_utc(session.absolute_expires_at) - ABSOLUTE_LIFETIME - timedelta(minutes=1)
    db_session.flush()
    with pytest.raises(AppError) as ei:
        svc.authenticate_request(raw, None, is_safe_method=True)
    assert ei.value.code == "SESSION_INVALID"


def test_genuine_activity_touches_but_never_extends_absolute(db_session, student):
    svc = AuthService(db_session)
    _, session, raw, csrf = svc.login("2026-AUTHTST", "student-pass-1")
    db_session.flush()
    before_absolute = session.absolute_expires_at
    svc.authenticate_request(raw, csrf, is_safe_method=False)  # genuine action
    db_session.flush()
    db_session.refresh(session)
    assert _as_utc(session.last_activity_at) >= _as_utc(session.created_at)
    # never slides: equal to the microsecond after normalization
    assert _as_utc(session.absolute_expires_at) == _as_utc(before_absolute)


def test_raw_credentials_never_stored(db_session, student):
    svc = AuthService(db_session)
    _, session, raw_credential, raw_csrf = svc.login("2026-AUTHTST", "student-pass-1")
    db_session.flush()
    assert len(session.token_hash) == 32
    assert len(session.csrf_token_hash) == 32
    assert session.token_hash == hashlib.sha256(raw_credential.encode()).digest()
    assert session.csrf_token_hash == hashlib.sha256(raw_csrf.encode()).digest()


# --------------------------------------------- one-time COR verification token


def _seed_screening(db_session, student, *, status="AWAITING_CONFIRMATION", token=None):
    from datetime import datetime, timezone

    from app.core.security import sha256_digest
    from app.modules.cor_screening.models import CorScreening

    profile = db_session.query(StudentProfile).filter_by(user_id=student.user_id).one()
    screening = CorScreening(
        student_user_id=student.user_id,
        status=status,
        format_template_version="test",
        submitted_at=datetime.now(timezone.utc),
        extracted_student_number="20231234-A",
        extracted_first_name="Ana",
        extracted_last_name="Santos",
        extracted_section="A",
        extracted_campus_id=profile.campus_id,
        extracted_program_id=profile.program_id,
        extracted_year_level=1,
        extracted_academic_period="2026-2027",
    )
    if token:
        screening.verification_token_hash = sha256_digest(token)
        screening.verification_token_issued_at = datetime.now(timezone.utc)
    db_session.add(screening)
    db_session.flush()
    return profile, screening


def _confirm_payload(profile) -> dict:
    return {
        "student_number": "20231234-A",
        "first_name": "Ana",
        "last_name": "Santos",
        "campus_id": profile.campus_id,
        "program_id": profile.program_id,
        "year_level": 1,
        "section": "A",
        "academic_period": "2026-2027",
    }


def _good_result():
    from app.modules.cor_screening import screening as engine

    return engine.ScreeningResult(
        fields=engine.ExtractedFields(
            student_no="20231234-A",
            name="Ana Santos",
            course="Test Program",
            year="1",
            section="A",
            campus="Test Campus",
            academic_period="2026-2027",
        ),
        method="text",
        format_score=1.0,
        extraction_confidence=1.0,
        missing=[],
        barcode_status=engine.BARCODE_DECODED,
        barcode_symbology="QRCode",
        barcode_payload="20231234-A",
        barcode_format_valid=True,
        barcode_student_number_match=True,
    )


def test_token_confirm_without_session_activates(client, db_session, student):
    token = "cor-token-confirm"
    profile, screening = _seed_screening(db_session, student, token=token)
    r = client.post(
        "/api/v1/cor-screenings/confirm",
        json=_confirm_payload(profile),
        headers={"X-COR-Token": token},
    )
    assert r.status_code == 200, r.text
    db_session.refresh(student)
    db_session.refresh(screening)
    assert student.account_status == "ACTIVE"
    assert screening.status == "PASSED"
    # The one-time token dies on activation.
    assert screening.verification_token_hash is None


def test_invalid_token_fails_closed_even_with_a_valid_session(client, db_session, student):
    profile, _screening = _seed_screening(db_session, student, token="real-token")
    login = _login(client, "auth-student@example.edu", "student-pass-1").json()
    r = client.post(
        "/api/v1/cor-screenings/confirm",
        json=_confirm_payload(profile),
        headers={"X-CSRF-Token": login["csrf_token"], "X-COR-Token": "bogus-token"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"


def test_empty_token_header_fails_closed_even_with_a_valid_session(client, db_session, student):
    """An empty X-COR-Token is a PRESENT (invalid) token, not 'no token'."""
    profile, screening = _seed_screening(db_session, student, token="real-token")
    login = _login(client, "auth-student@example.edu", "student-pass-1").json()
    r = client.post(
        "/api/v1/cor-screenings/confirm",
        json=_confirm_payload(profile),
        headers={"X-CSRF-Token": login["csrf_token"], "X-COR-Token": ""},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"
    # The session path must not have activated the account.
    db_session.refresh(student)
    assert student.account_status == "PENDING_VERIFICATION"


def test_token_reject_marks_needs_resubmission(client, db_session, student):
    token = "cor-token-reject"
    _profile, screening = _seed_screening(db_session, student, token=token)
    r = client.post("/api/v1/cor-screenings/reject", headers={"X-COR-Token": token})
    assert r.status_code == 200, r.text
    db_session.refresh(screening)
    assert screening.status == "NEEDS_RESUBMISSION"
    assert screening.failure_reason_code == "REJECTED_BY_STUDENT"


def test_token_resubmit_rotates_the_token(client, db_session, student, monkeypatch):
    from app.core.security import sha256_digest
    from app.modules.cor_screening import screening as engine

    monkeypatch.setattr(engine, "ensure_dependencies", lambda settings: None)
    monkeypatch.setattr(engine, "screen_pdf", lambda path, settings: _good_result())

    token = "cor-token-resubmit"
    _profile, screening = _seed_screening(
        db_session, student, status="NEEDS_RESUBMISSION", token=token
    )
    r = client.post(
        "/api/v1/cor-screenings/resubmit",
        files={"file": ("cor.pdf", b"%PDF-1.4 test", "application/pdf")},
        headers={"X-COR-Token": token},
    )
    assert r.status_code == 201, r.text
    rotated = r.json()["verification_token"]
    assert rotated and rotated != token
    db_session.refresh(screening)
    assert screening.verification_token_hash == sha256_digest(rotated)

    # The old token is dead; the rotated token authorizes the next action.
    reject = client.post("/api/v1/cor-screenings/reject", headers={"X-COR-Token": token})
    assert reject.status_code == 401
    assert reject.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"


# --------------------------------------------------- profile edit requests


def test_token_request_edit_activates_and_queues(client, db_session, student):
    token = "cor-token-edit"
    profile, _screening = _seed_screening(db_session, student, token=token)
    payload = _confirm_payload(profile)
    payload["last_name"] = "Reyes"

    r = client.post(
        "/api/v1/cor-screenings/request-edit",
        json=payload,
        headers={"X-COR-Token": token},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["change_request"] is not None
    assert body["change_request"]["requested_last_name"] == "Reyes"
    db_session.refresh(student)
    assert student.account_status == "ACTIVE"


def test_superadmin_reviews_pending_edit(client, db_session, student, superadmin):
    token = "cor-token-edit-review"
    profile, _screening = _seed_screening(db_session, student, token=token)
    payload = _confirm_payload(profile)
    payload["last_name"] = "Reyes"
    created = client.post(
        "/api/v1/cor-screenings/request-edit",
        json=payload,
        headers={"X-COR-Token": token},
    )
    assert created.status_code == 200, created.text

    # Activation used the COR value; the requested change is only pending.
    db_session.refresh(student)
    assert student.last_name == "Santos"

    login = _login(client, "auth-super@example.edu", "super-pass-1").json()
    listing = client.get("/api/v1/profile-change-requests?status=PENDING").json()
    assert listing["total"] == 1
    change_request_id = listing["items"][0]["change_request"]["change_request_id"]

    approved = client.post(
        f"/api/v1/profile-change-requests/{change_request_id}/approve",
        headers={"X-CSRF-Token": login["csrf_token"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    db_session.refresh(student)
    assert student.last_name == "Reyes"


def test_counselor_cannot_review_profile_edits(client, counselor):
    login = _login(client, "auth-counselor@example.edu", "counselor-pass-1").json()
    r = client.get(
        "/api/v1/profile-change-requests",
        headers={"X-CSRF-Token": login["csrf_token"]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_counselor_cannot_approve_a_profile_edit(client, db_session, student, counselor):
    token = "cor-token-edit-counselor"
    profile, _screening = _seed_screening(db_session, student, token=token)
    payload = _confirm_payload(profile)
    payload["last_name"] = "Reyes"
    created = client.post(
        "/api/v1/cor-screenings/request-edit",
        json=payload,
        headers={"X-COR-Token": token},
    )
    assert created.status_code == 200, created.text
    change_request_id = created.json()["change_request"]["change_request_id"]

    login = _login(client, "auth-counselor@example.edu", "counselor-pass-1").json()
    r = client.post(
        f"/api/v1/profile-change-requests/{change_request_id}/approve",
        headers={"X-CSRF-Token": login["csrf_token"]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_request_edit_rejects_invalid_token(client, db_session, student):
    _seed_screening(db_session, student, token="real-token")
    r = client.post(
        "/api/v1/cor-screenings/request-edit",
        json={
            "student_number": "20231234-A",
            "first_name": "Ana",
            "last_name": "Santos",
            "campus_id": 1,
            "program_id": 1,
            "year_level": 1,
            "section": "A",
            "academic_period": "2026-2027",
        },
        headers={"X-COR-Token": "bogus-token"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"


def test_token_reject_account_deletes_the_account(client, db_session, student):
    from sqlalchemy import select

    token = "cor-token-reject-account"
    _seed_screening(db_session, student, token=token)
    user_id = student.user_id

    r = client.post(
        "/api/v1/cor-screenings/reject-account", headers={"X-COR-Token": token}
    )
    assert r.status_code == 204
    assert db_session.scalars(select(User).where(User.user_id == user_id)).first() is None


def test_reject_account_requires_a_valid_token(client, db_session, student):
    _seed_screening(db_session, student, token="real-token")
    r = client.post(
        "/api/v1/cor-screenings/reject-account", headers={"X-COR-Token": "bogus"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_VERIFICATION_TOKEN"


def test_counselor_cannot_reject_an_account(client, counselor):
    login = _login(client, "auth-counselor@example.edu", "counselor-pass-1").json()
    r = client.post(
        "/api/v1/cor-screenings/reject-account",
        headers={"X-CSRF-Token": login["csrf_token"]},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN_ROLE"
