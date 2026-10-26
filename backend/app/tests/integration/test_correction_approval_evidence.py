"""Approval independently verifies exact evidence and reviewer eligibility."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import event, func, select

from app.modules.accounts.models import User
from app.modules.accounts.repository import AccountsRepository
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService, as_utc
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_availability import evidence  # noqa: F401
from .test_correction_approval_version import csrf


def approve(client, request):
    return client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/approve",
                       headers=csrf(client), json={"submission_version": 1})


@pytest.mark.parametrize("case,availability", [
    ("metadata", "UNAVAILABLE"), ("bytes", "UNAVAILABLE"), ("cleanup", "UNAVAILABLE"),
    ("digest_metadata", "UNAVAILABLE"), ("upload", "UNAVAILABLE"), ("purpose", "UNAVAILABLE"),
    ("owner", "UNAVAILABLE"), ("mime", "UNAVAILABLE"), ("path", "UNAVAILABLE"),
    ("unconfirmed", "UNAVAILABLE"), ("corrupt", "CORRUPT"), ("signature", "CORRUPT"), ("size", "CORRUPT"),
    ("expired", "EXPIRED"), ("file_expired", "EXPIRED"), ("upload_cap", "EXPIRED"),
    ("screening_cap", "EXPIRED"), ("replacement", "REPLACED"), ("new_file", "REPLACED"),
])
def test_unusable_evidence_cannot_approve_or_change_any_business_state(db_session, db_client, evidence, case, availability, caplog):
    _, user, screening, profile, request, file, path = evidence
    now = datetime.now(timezone.utc)
    if case == "metadata":
        db_session.delete(file)
    elif case == "bytes":
        path.unlink()
    elif case == "cleanup":
        file.cleanup_state = "FAILED"
    elif case == "digest_metadata":
        file.sha256_hash = b"x" * 32
    elif case == "upload":
        file.uploaded_at = as_utc(file.uploaded_at) + timedelta(seconds=1)
    elif case == "purpose":
        screening.purpose = "CORRECTION"
    elif case == "owner":
        screening.student_user_id = db_session.scalar(select(User.user_id).where(User.role_code == "SUPERADMIN"))
    elif case == "mime":
        file.mime_type = "text/plain"
    elif case == "path":
        file.storage_key = "../PRIVATE-OUTSIDE.pdf"
    elif case == "unconfirmed":
        screening.confirmed_at = None
    elif case == "corrupt":
        path.write_bytes(b"%PDF PRIVATE-ALTERED")
    elif case == "signature":
        import hashlib
        content = b"PRIVATE-NOT-PDF"
        path.write_bytes(content)
        file.sha256_hash = request.evidence_sha256_hash = hashlib.sha256(content).digest()
        file.size_bytes = len(content)
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
    elif case == "screening_cap":
        screening.submitted_at = now - timedelta(days=8)
    elif case == "replacement":
        db_session.add(CorScreening(student_user_id=user.user_id, purpose="REGISTRATION", status="AWAITING_CONFIRMATION",
            format_template_version="test", submitted_at=now + timedelta(seconds=1)))
    else:
        db_session.add(CorScreeningFile(cor_screening_id=screening.cor_screening_id,
            storage_key="cor/PRIVATE-NEW.pdf", original_filename="replacement.pdf", mime_type="application/pdf",
            size_bytes=file.size_bytes, sha256_hash=file.sha256_hash, cleanup_state="PENDING",
            uploaded_at=now, expires_at=now + timedelta(days=7)))
    db_session.commit()
    original_deadline = request.evidence_expires_at
    original_validity = screening.valid_until
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    existed = path.exists()
    response = approve(db_client, request)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "COR_EVIDENCE_UNAVAILABLE"
    assert error["details"]["availability"] == availability
    assert set(error["details"]) == {"availability", "expires_at"}
    for secret in ("PRIVATE-OUTSIDE", "PRIVATE-ALTERED", "PRIVATE-NOT-PDF", str(path), file.storage_key,
                   file.original_filename, "evidence_file_id", "sha256_hash"):
        assert secret not in response.text + caplog.text
    db_session.refresh(request)
    db_session.refresh(profile)
    assert request.status == "PENDING" and request.reviewed_by_user_id is request.reviewed_at is None
    assert as_utc(request.evidence_expires_at) == as_utc(original_deadline) and screening.valid_until == original_validity
    assert user.account_status == "ACTIVE" and (user.first_name, user.last_name) == ("Juan", "Cruz")
    assert profile.section == "A" and profile.year_level == 1
    assert path.exists() == existed
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == count


def test_prior_preview_does_not_authorize_modified_pdf(db_client, evidence):
    _, _, _, _, request, _, path = evidence
    preview = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}/cor")
    assert preview.status_code == 200
    path.write_bytes(b"%PDF CHANGED-AFTER-PREVIEW")
    response = approve(db_client, request)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["availability"] == "CORRUPT"


@pytest.mark.parametrize("field,value,code", [("is_deactivated", True, "ACCOUNT_DEACTIVATED"),
    ("account_status", "VERIFICATION_EXPIRED", "FORBIDDEN_ROLE"), ("role_code", "GUIDANCE_STAFF", "FORBIDDEN_ROLE")])
def test_fresh_reviewer_lock_precedes_evidence_and_application(db_session, db_client, evidence, monkeypatch, field, value, code):
    _, _, _, profile, request, _, path = evidence
    original = AccountsRepository.lock_user

    def changed(self, user_id):
        row = original(self, user_id)
        if row.role_code == "SUPERADMIN":
            setattr(row, field, value)
        return row

    def forbidden(*args, **kwargs):
        pytest.fail("Ineligible reviewer reached private evidence")

    monkeypatch.setattr(AccountsRepository, "lock_user", changed)
    monkeypatch.setattr(CorScreeningService, "inspect_correction_evidence", forbidden)
    response = approve(db_client, request)
    assert response.status_code == 403 and response.json()["error"]["code"] == code
    assert request.status == "PENDING" and profile.section == "A" and path.exists()


def test_approval_uses_current_file_reads_in_established_lock_order(db_session, db_client, evidence):
    _, _, _, profile, request, _, path = evidence
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if "FOR UPDATE" in statement:
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = approve(db_client, request)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200
    # HTTP authentication now locks User -> session and commits before
    # the separate reviewer -> Student -> evidence domain transaction.
    auth_end = max(index for index, sql in enumerate(statements) if "FROM user_sessions" in sql)
    assert "FROM users" in statements[auth_end - 1]
    statements = statements[auth_end + 1:]
    assert "FROM users" in statements[0] and "FROM users" in statements[1]
    assert "FROM cor_screenings" in statements[2]
    assert "FROM profile_change_requests" in statements[3]
    assert any("FROM cor_screening_files" in statement for statement in statements[4:])
    assert profile.section == "B" and request.status == "APPROVED" and not path.exists()


def test_expiry_during_evidence_read_denies_approval(db_client, evidence, monkeypatch):
    _, _, _, profile, request, _, path = evidence
    deadline = as_utc(request.evidence_expires_at)
    ticks = iter([deadline - timedelta(seconds=1), deadline])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(ticks)

    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    response = approve(db_client, request)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["availability"] == "EXPIRED"
    assert request.status == "PENDING" and profile.section == "A" and path.exists()


def test_storage_error_denies_approval_without_logging_details(db_client, evidence, monkeypatch, caplog):
    _, _, _, profile, request, _, path = evidence
    original = Path.open

    def denied(target, *args, **kwargs):
        if target == path:
            raise PermissionError("PRIVATE-STORAGE-FAILURE")
        return original(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    response = approve(db_client, request)
    assert response.status_code == 409 and profile.section == "A" and request.status == "PENDING"
    assert "PRIVATE-STORAGE-FAILURE" not in response.text + caplog.text


def test_changed_owner_or_screening_during_lock_is_stale(db_session, db_client, evidence, monkeypatch):
    _, user, _, profile, request, _, path = evidence
    another = CorScreening(student_user_id=user.user_id, purpose="CORRECTION", status="PASSED",
                           format_template_version="test", submitted_at=datetime.now(timezone.utc))
    db_session.add(another)
    db_session.flush()
    original = ProfileChangeService._lock_request_after_student

    def changed(self, request_id):
        row = original(self, request_id)
        row.cor_screening_id = another.cor_screening_id
        return row

    def forbidden(*args, **kwargs):
        pytest.fail("Changed context reached evidence")

    monkeypatch.setattr(ProfileChangeService, "_lock_request_after_student", changed)
    monkeypatch.setattr(CorScreeningService, "inspect_correction_evidence", forbidden)
    response = approve(db_client, request)
    assert response.status_code == 409 and response.json()["error"]["code"] == "CHANGE_REQUEST_STALE"
    assert profile.section == "A" and request.status == "PENDING" and path.exists()
