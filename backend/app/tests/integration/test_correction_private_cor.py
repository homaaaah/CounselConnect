"""Authenticated exact private PDF delivery, errors and verified-byte reuse."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import event, func, select

from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService, as_utc
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_student_correction_reads import login


def preview(client, request):
    return client.get(f"/api/v1/profile-change-requests/{request.change_request_id}/cor")


def test_pdf_is_exact_private_nostore_and_does_not_change_business_state(db_session, db_client, evidence):
    _, user, screening, profile, request, file, path = evidence
    original = path.read_bytes()
    deadline = request.evidence_expires_at
    audit_count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = preview(db_client, request)
    assert response.status_code == 200
    assert response.content == original
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == 'inline; filename="registration-correction-cor.pdf"'
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "etag" not in response.headers and "last-modified" not in response.headers
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count
    db_session.refresh(request)
    assert request.status == "PENDING" and request.evidence_expires_at == deadline
    assert user.account_status == "ACTIVE" and profile.section == "A" and screening.status == "PASSED"
    assert path.exists() and db_session.get(CorScreeningFile, file.cor_screening_file_id) is not None


def test_response_uses_same_verified_bytes_without_second_path_read(db_client, evidence, monkeypatch):
    service, _, _, _, request, _, path = evidence
    original_bytes = path.read_bytes()
    inspect = service.__class__.inspect_correction_evidence
    calls = []

    def inspect_then_change(self, row, *, lock=False):
        calls.append(lock)
        result = inspect(self, row, lock=lock)
        path.write_bytes(b"%PDF PRIVATE-UNVERIFIED-REPLACEMENT")
        return result

    monkeypatch.setattr(service.__class__, "inspect_correction_evidence", inspect_then_change)
    response = preview(db_client, request)
    assert response.status_code == 200 and response.content == original_bytes
    assert b"PRIVATE-UNVERIFIED" not in response.content
    assert calls == [True]


def test_get_locks_reviewer_student_screening_request_then_file(db_session, db_client, evidence):
    _, _, _, _, request, _, _ = evidence
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _many):
        if "FOR UPDATE" in statement:
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = preview(db_client, request)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200
    # Ignore the completed HTTP auth transaction, while verifying its order.
    auth_end = max(index for index, sql in enumerate(statements) if "FROM user_sessions" in sql)
    assert "FROM users" in statements[auth_end - 1]
    statements = statements[auth_end + 1:]
    assert "FROM users" in statements[0] and "FROM users" in statements[1]
    assert "FROM cor_screenings" in statements[2]
    assert "FROM profile_change_requests" in statements[3]
    assert any("FROM cor_screening_files" in statement for statement in statements[4:])


@pytest.mark.parametrize("role", ["STUDENT", "COUNSELOR", "GUIDANCE_STAFF"])
def test_other_roles_denied_before_evidence_lookup(db_session, db_client, evidence, monkeypatch, role):
    _, student, _, _, request, _, _ = evidence
    if role == "STUDENT":
        actor = student
    else:
        actor = User(email="private-staff@example.edu", password_hash=hash_password("password1"),
                     role_code=role, account_status="ACTIVE", first_name="Staff", last_name="Reader")
        db_session.add(actor)
        db_session.commit()
    login(db_client, actor.email)

    def forbidden(*args, **kwargs):
        pytest.fail("Other role reached evidence query")

    monkeypatch.setattr("app.modules.profile_change.repository.ProfileChangeRepository.get", forbidden)
    response = preview(db_client, request)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"
    assert response.headers["cache-control"] == "no-store"


def test_anonymous_and_cor_token_only_cannot_preview(db_client, evidence):
    _, _, _, _, request, _, _ = evidence
    db_client.cookies.clear()
    for headers in ({}, {"X-COR-Token": "PRIVATE-NOT-A-SESSION"}):
        response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}/cor", headers=headers)
        assert response.status_code == 401
        assert b"%PDF" not in response.content
        assert "PRIVATE-NOT-A-SESSION" not in response.text


@pytest.mark.parametrize("field,value,code", [("is_deactivated", True, "ACCOUNT_DEACTIVATED"),
    ("account_status", "PENDING_VERIFICATION", "FORBIDDEN_ROLE"),
    ("account_status", "VERIFICATION_EXPIRED", "FORBIDDEN_ROLE")])
def test_ineligible_superadmin_denied(db_session, db_client, evidence, field, value, code):
    _, _, _, _, request, _, _ = evidence
    actor = db_session.scalar(select(User).where(User.role_code == "SUPERADMIN"))
    setattr(actor, field, value)
    db_session.commit()
    response = preview(db_client, request)
    assert response.status_code == 403 and response.json()["error"]["code"] == code


def test_reviewer_rechecked_under_account_lock(db_session, db_client, evidence, monkeypatch):
    _, _, _, _, request, _, _ = evidence
    from app.modules.accounts.repository import AccountsRepository
    original = AccountsRepository.lock_user

    def changed(self, user_id):
        row = original(self, user_id)
        if row.role_code == "SUPERADMIN":
            row.is_deactivated = True
        return row

    monkeypatch.setattr(AccountsRepository, "lock_user", changed)
    response = preview(db_client, request)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"


@pytest.mark.parametrize("case,code", [
    ("legacy", "LEGACY_UNKNOWN"), ("approved", "RESOLVED"), ("returned", "RESOLVED"), ("rejected", "RESOLVED"),
    ("missing_metadata", "UNAVAILABLE"), ("missing_bytes", "UNAVAILABLE"), ("cleanup_failed", "UNAVAILABLE"),
    ("digest_metadata", "UNAVAILABLE"), ("upload", "UNAVAILABLE"), ("mime", "UNAVAILABLE"),
    ("purpose", "UNAVAILABLE"), ("owner", "UNAVAILABLE"), ("unconfirmed", "UNAVAILABLE"),
    ("path", "UNAVAILABLE"), ("corrupt", "CORRUPT"), ("size", "CORRUPT"),
    ("expired", "EXPIRED"), ("file_expired", "EXPIRED"), ("upload_cap", "EXPIRED"),
    ("replacement", "REPLACED"), ("new_file", "REPLACED"),
])
def test_unusable_evidence_safe_409_without_pdf_or_private_metadata(db_session, db_client, evidence, case, code, caplog):
    _, user, screening, _, request, file, path = evidence
    now = datetime.now(timezone.utc)
    if case == "legacy":
        request.submission_version = None
    elif case in ("approved", "returned", "rejected"):
        request.status = {"approved": "APPROVED", "returned": "RETURNED", "rejected": "REJECTED"}[case]
    elif case == "missing_metadata":
        db_session.delete(file)
    elif case == "missing_bytes":
        path.unlink()
    elif case == "cleanup_failed":
        file.cleanup_state = "FAILED"
    elif case == "digest_metadata":
        file.sha256_hash = b"x" * 32
    elif case == "upload":
        file.uploaded_at = as_utc(file.uploaded_at) + timedelta(seconds=1)
    elif case == "mime":
        file.mime_type = "text/plain"
    elif case == "purpose":
        screening.purpose = "CORRECTION"
    elif case == "owner":
        screening.student_user_id = db_session.scalar(select(User.user_id).where(User.role_code == "SUPERADMIN"))
    elif case == "unconfirmed":
        screening.confirmed_at = None
    elif case == "path":
        file.storage_key = "../PRIVATE-OUTSIDE.pdf"
    elif case == "corrupt":
        path.write_bytes(b"%PDF PRIVATE-ALTERED-BYTES")
    elif case == "size":
        file.size_bytes += 1
    elif case == "expired":
        request.evidence_uploaded_at = now - timedelta(days=2)
        request.evidence_expires_at = now - timedelta(seconds=1)
    elif case == "file_expired":
        file.expires_at = now - timedelta(seconds=1)
    elif case == "upload_cap":
        request.evidence_uploaded_at = file.uploaded_at = now - timedelta(days=8)
        request.evidence_expires_at = file.expires_at = now + timedelta(days=1)
    elif case == "replacement":
        db_session.add(CorScreening(student_user_id=user.user_id, purpose="REGISTRATION", status="AWAITING_CONFIRMATION",
            format_template_version="test", submitted_at=now + timedelta(seconds=1)))
    else:
        db_session.add(CorScreeningFile(cor_screening_id=screening.cor_screening_id,
            storage_key="cor/PRIVATE-NEW.pdf", original_filename="replacement.pdf", mime_type="application/pdf",
            size_bytes=file.size_bytes, sha256_hash=file.sha256_hash, cleanup_state="PENDING",
            uploaded_at=now, expires_at=now + timedelta(days=7)))
    db_session.commit()
    response = preview(db_client, request)
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    error = response.json()["error"]
    assert error["code"] == "COR_EVIDENCE_UNAVAILABLE"
    assert error["details"]["availability"] == code
    assert set(error["details"]) == {"availability", "expires_at"}
    assert b"%PDF" not in response.content
    for secret in ("PRIVATE-OUTSIDE", "PRIVATE-ALTERED", str(path), file.storage_key, file.original_filename,
                   "evidence_file_id", "sha256_hash", "storage_key"):
        assert secret not in response.text + caplog.text


def test_prior_available_detail_does_not_authorize_changed_bytes(db_client, evidence):
    _, _, _, _, request, _, path = evidence
    assert db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}").json()["evidence"]["availability"] == "AVAILABLE"
    path.write_bytes(b"%PDF CHANGED-AFTER-DETAIL")
    response = preview(db_client, request)
    assert response.status_code == 409 and response.json()["error"]["details"]["availability"] == "CORRUPT"


def test_locked_request_state_is_used_instead_of_earlier_pending_lookup(db_client, evidence, monkeypatch):
    _, _, _, _, request, _, _ = evidence
    from app.modules.profile_change.repository import ProfileChangeRepository
    original = ProfileChangeRepository.lock_by_id

    def returned(self, request_id):
        row = original(self, request_id)
        row.status = "RETURNED"
        return row

    monkeypatch.setattr(ProfileChangeRepository, "lock_by_id", returned)
    response = preview(db_client, request)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["availability"] == "RESOLVED"


def test_changed_context_after_lock_is_denied_without_private_read(db_session, db_client, evidence, monkeypatch):
    service, user, _, _, request, _, _ = evidence
    newer = CorScreening(student_user_id=user.user_id, purpose="CORRECTION", status="PASSED",
                         format_template_version="test", submitted_at=datetime.now(timezone.utc))
    db_session.add(newer)
    db_session.flush()
    from app.modules.profile_change.service import ProfileChangeService
    original = ProfileChangeService._lock_request_after_student

    def moved(self, request_id):
        row = original(self, request_id)
        row.cor_screening_id = newer.cor_screening_id
        return row

    def forbidden(*args, **kwargs):
        pytest.fail("Changed context reached private storage")

    monkeypatch.setattr(ProfileChangeService, "_lock_request_after_student", moved)
    monkeypatch.setattr(service.__class__, "_storage_path", forbidden)
    response = preview(db_client, request)
    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"availability": "UNAVAILABLE", "expires_at": None}


def test_storage_failure_does_not_escape_safe_envelope(db_client, evidence, monkeypatch, caplog):
    _, _, _, _, request, _, path = evidence
    original_open = Path.open

    def denied(target, *args, **kwargs):
        if target == path:
            raise PermissionError("PRIVATE-STORAGE-FAILURE")
        return original_open(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    response = preview(db_client, request)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["availability"] == "UNAVAILABLE"
    assert "PRIVATE-STORAGE-FAILURE" not in response.text + caplog.text


def test_expiry_while_reading_denies_pdf(db_client, evidence, monkeypatch):
    _, _, _, _, request, _, _ = evidence
    deadline = as_utc(request.evidence_expires_at)
    ticks = iter([deadline - timedelta(seconds=1), deadline])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(ticks)

    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    response = preview(db_client, request)
    assert response.status_code == 409 and response.json()["error"]["details"]["availability"] == "EXPIRED"
    assert b"%PDF" not in response.content


def test_missing_request_safe_404(db_client, evidence):
    response = db_client.get("/api/v1/profile-change-requests/999999999/cor")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_NOT_FOUND"
    assert response.headers["cache-control"] == "no-store"
