"""Exact pending evidence availability via authorized Superadmin detail reads."""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.accounts.models import User
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import as_utc
from .test_correction_evidence_retention import pending
from .test_profile_change import _superadmin
from .test_student_correction_reads import login


@pytest.fixture
def evidence(db_session, db_client, academic_references, monkeypatch):
    values = pending(db_session, academic_references, monkeypatch)
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    return values


def status(client, request):
    response = client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return response.json()["evidence"]


def test_available_requires_bytes_and_preserves_original_deadline_and_state(db_session, db_client, evidence, caplog):
    service, user, screening, profile, request, file, path = evidence
    before = db_session.scalar(select(func.count()).select_from(AuditEvent))
    original = request.evidence_expires_at
    body = status(db_client, request)
    assert set(body) == {"availability", "expires_at"}
    assert body["availability"] == "AVAILABLE"
    assert body["expires_at"].endswith("Z")
    assert datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")) == min(
        as_utc(original), as_utc(file.uploaded_at) + timedelta(days=7),
        as_utc(screening.submitted_at) + timedelta(days=7), as_utc(file.expires_at))
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
    db_session.refresh(request)
    assert request.status == "PENDING" and request.evidence_expires_at == original
    assert user.account_status == "ACTIVE" and profile.section == "A" and path.exists()
    assert str(path) not in caplog.text and file.storage_key not in caplog.text


@pytest.mark.parametrize("missing", ["evidence_file_id", "evidence_sha256_hash", "evidence_uploaded_at", "evidence_expires_at"])
def test_partial_evidence_metadata_is_unavailable(db_session, db_client, evidence, missing):
    *_, request, file, path = evidence
    setattr(request, missing, None)
    db_session.commit()
    assert status(db_client, request)["availability"] == "UNAVAILABLE"
    assert path.exists()


def test_unknown_legacy_pending_does_not_infer_evidence(db_session, db_client, evidence, monkeypatch):
    service, _, _, _, request, _, _ = evidence
    request.submission_version = None
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Legacy unknown evidence reached private storage")

    monkeypatch.setattr(service.__class__, "_storage_path", forbidden)
    assert status(db_client, request) == {"availability": "LEGACY_UNKNOWN", "expires_at": None}


@pytest.mark.parametrize("terminal", ["APPROVED", "RETURNED", "REJECTED"])
def test_resolved_evidence_is_never_read_even_when_bytes_remain(db_session, db_client, evidence, monkeypatch, terminal):
    service, _, _, _, request, _, path = evidence
    request.status = terminal
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Resolved evidence reached private storage")

    monkeypatch.setattr(service.__class__, "_storage_path", forbidden)
    assert status(db_client, request)["availability"] == "RESOLVED"
    assert path.exists()


@pytest.mark.parametrize("deadline", ["request", "file", "upload_cap", "screening_cap"])
def test_expiry_is_independent_of_cleanup_and_never_restricts_enrollment(db_session, db_client, evidence, deadline):
    _, user, screening, profile, request, file, path = evidence
    now = datetime.now(timezone.utc)
    if deadline == "request":
        request.evidence_uploaded_at = now - timedelta(days=2)
        request.evidence_expires_at = now - timedelta(seconds=1)
    elif deadline == "file":
        file.expires_at = now - timedelta(seconds=1)
    elif deadline == "upload_cap":
        request.evidence_uploaded_at = file.uploaded_at = now - timedelta(days=8)
        request.evidence_expires_at = file.expires_at = now + timedelta(days=10)
    else:
        screening.submitted_at = now - timedelta(days=8)
    db_session.commit()
    assert status(db_client, request)["availability"] == "EXPIRED"
    db_session.refresh(request)
    assert request.status == "PENDING" and path.exists()
    assert user.account_status == "ACTIVE" and profile.section == "A"


def test_expiry_at_exact_deadline(db_client, evidence, monkeypatch):
    _, _, _, _, request, _, _ = evidence
    moment = as_utc(request.evidence_expires_at)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    assert status(db_client, request)["availability"] == "EXPIRED"


@pytest.mark.parametrize("bad", ["missing_metadata", "missing_bytes", "cleanup_failed", "digest", "upload", "mime", "path"])
def test_unusable_exact_evidence_is_unavailable_without_leaks(db_session, db_client, evidence, bad, caplog):
    service, _, _, _, request, file, path = evidence
    if bad == "missing_metadata":
        db_session.delete(file)
    elif bad == "missing_bytes":
        path.unlink()
    elif bad == "cleanup_failed":
        file.cleanup_state = "FAILED"
    elif bad == "digest":
        file.sha256_hash = b"x" * 32
    elif bad == "upload":
        file.uploaded_at = as_utc(file.uploaded_at) + timedelta(seconds=1)
    elif bad == "mime":
        file.mime_type = "text/plain"
    else:
        file.storage_key = "../PRIVATE-OUTSIDE.pdf"
    db_session.commit()
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    assert response.json()["evidence"]["availability"] == "UNAVAILABLE"
    for secret in ("PRIVATE-OUTSIDE", str(path), file.storage_key, file.original_filename,
                   "sha256_hash", "evidence_file_id", "storage_key"):
        assert secret not in response.text + caplog.text


@pytest.mark.parametrize("corruption", ["digest", "size", "signature", "oversize_metadata", "oversize_bytes"])
def test_actual_corruption_fails_closed(db_session, db_client, evidence, corruption):
    _, _, _, _, request, file, path = evidence
    if corruption == "digest":
        path.write_bytes(b"%PDF altered")
        file.size_bytes = len(path.read_bytes())
    elif corruption == "size":
        file.size_bytes += 1
    elif corruption == "signature":
        content = b"PRIVATE-NOT-PDF"
        path.write_bytes(content)
        file.size_bytes = len(content)
        file.sha256_hash = request.evidence_sha256_hash = hashlib.sha256(content).digest()
    elif corruption == "oversize_metadata":
        file.size_bytes = 10 * 1024 * 1024 + 1
    else:
        path.write_bytes(b"%PDF" + b"x" * (10 * 1024 * 1024))
    db_session.commit()
    assert status(db_client, request)["availability"] == "CORRUPT"


@pytest.mark.parametrize("replacement", ["new_screening", "new_file", "screening_state"])
def test_replacement_never_substitutes_latest_evidence(db_session, db_client, evidence, replacement):
    _, user, screening, _, request, file, path = evidence
    now = datetime.now(timezone.utc)
    if replacement == "new_screening":
        db_session.add(CorScreening(student_user_id=user.user_id, purpose="REGISTRATION", status="AWAITING_CONFIRMATION",
            format_template_version="test", submitted_at=now + timedelta(seconds=1)))
    elif replacement == "screening_state":
        screening.status = "NEEDS_RESUBMISSION"
    else:
        db_session.add(CorScreeningFile(cor_screening_id=screening.cor_screening_id,
            storage_key="cor/PRIVATE-REPLACEMENT.pdf", original_filename="replacement.pdf", mime_type="application/pdf",
            size_bytes=file.size_bytes, sha256_hash=file.sha256_hash, cleanup_state="PENDING",
            uploaded_at=now, expires_at=now + timedelta(days=7)))
    db_session.commit()
    assert status(db_client, request)["availability"] == "REPLACED"
    assert path.exists() and request.status == "PENDING"


@pytest.mark.parametrize("mismatch", ["owner", "purpose", "file_screening", "unconfirmed"])
def test_evidence_context_mismatch_is_unavailable(db_session, db_client, evidence, mismatch):
    _, user, screening, _, request, file, _ = evidence
    if mismatch == "owner":
        screening.student_user_id = db_session.scalar(select(User.user_id).where(User.role_code == "SUPERADMIN"))
    elif mismatch == "purpose":
        screening.purpose = "CORRECTION"
    elif mismatch == "unconfirmed":
        screening.confirmed_at = None
    else:
        another = CorScreening(student_user_id=user.user_id, status="PASSED", purpose="CORRECTION",
                               format_template_version="test", submitted_at=datetime.now(timezone.utc))
        db_session.add(another)
        db_session.flush()
        file.cor_screening_id = another.cor_screening_id
    db_session.commit()
    assert status(db_client, request)["availability"] == "UNAVAILABLE"


def test_storage_error_is_safe_and_preserves_bytes(db_client, evidence, monkeypatch, caplog):
    _, _, _, _, request, _, path = evidence
    original_open = Path.open

    def denied(target, *args, **kwargs):
        if target == path:
            raise PermissionError("PRIVATE-STORAGE-FAILURE")
        return original_open(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    assert status(db_client, request)["availability"] == "UNAVAILABLE"
    assert "PRIVATE-STORAGE-FAILURE" not in caplog.text
    assert path.exists()


def test_expiry_while_reading_is_rechecked(db_client, evidence, monkeypatch):
    _, _, _, _, request, _, _ = evidence
    deadline = as_utc(request.evidence_expires_at)
    ticks = iter([deadline - timedelta(seconds=1), deadline])

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return next(ticks)

    monkeypatch.setattr("app.modules.cor_screening.service.datetime", Clock)
    assert status(db_client, request)["availability"] == "EXPIRED"


def test_student_detail_never_inspects_or_exposes_private_evidence(db_client, evidence, monkeypatch):
    service, user, _, _, request, _, _ = evidence
    login(db_client, user.email)

    def forbidden(*args, **kwargs):
        pytest.fail("Student detail inspected private evidence")

    monkeypatch.setattr(service.__class__, "correction_evidence_status", forbidden)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    assert "evidence" not in response.json()
