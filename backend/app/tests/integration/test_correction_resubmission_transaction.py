"""Atomic fresh evidence and immutable linked correction-version creation."""

from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from pymysql.err import IntegrityError as MysqlIntegrityError, OperationalError as MysqlOperationalError

from app.core.exceptions import AppError
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService, SEVEN_DAYS, as_utc
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_resubmission_preflight import returned_context  # noqa: F401


def revise(db, values):
    _, user, _, _, previous, _, _ = values
    return ProfileChangeService(db).resubmit(user, previous.change_request_id,
        submission_version=previous.submission_version, proposed_changes='{"section":" B "}',
        content=b"%PDF-1.4 fresh revision", filename="revision.pdf")


def counts(db):
    return tuple(db.scalar(select(func.count()).select_from(model)) for model in
                 (CorScreening, CorScreeningFile, ProfileChangeRequest, AuditEvent))


@pytest.fixture
def stored_paths(monkeypatch):
    paths = []
    store = CorScreeningService._store_cor_bytes
    def capture(self, content):
        key = store(self, content)
        paths.append(Path(self._storage_path(key)))
        return key
    monkeypatch.setattr(CorScreeningService, "_store_cor_bytes", capture)
    return paths


@pytest.mark.parametrize("legacy", [False, True])
def test_new_version_has_exact_fresh_proof_current_baseline_and_unchanged_history(
    db_session, returned_context, stored_paths, legacy,
):
    service, user, enrolled, profile, previous, _, _ = returned_context
    if legacy:
        previous.submission_version = None
        previous.status = "REJECTED"
        previous.registered_values_json = previous.extracted_values_json = None
    profile.section = "CURRENT"
    db_session.commit()
    original = deepcopy((previous.status, previous.decision_reason, previous.registered_values_json,
                         previous.extracted_values_json, previous.requested_section, as_utc(previous.reviewed_at)))
    enrolled_state = enrolled.status, enrolled.valid_until, as_utc(enrolled.confirmed_at)
    row = revise(db_session, returned_context)
    assert row.change_request_id != previous.change_request_id
    assert row.submission_version == (1 if legacy else 2)
    assert row.previous_change_request_id == row.root_change_request_id == previous.change_request_id
    assert row.registered_cor_screening_id == enrolled.cor_screening_id
    assert row.registered_values_json["section"] == "CURRENT"
    assert row.requested_section == "B" and row.status == "PENDING"
    proof = db_session.get(CorScreening, row.cor_screening_id)
    file = db_session.get(CorScreeningFile, row.evidence_file_id)
    assert proof.purpose == "CORRECTION" and proof.status == "PASSED"
    assert proof.confirmed_at is proof.valid_until is proof.verification_token_hash is None
    assert as_utc(file.uploaded_at) == as_utc(proof.submitted_at) == as_utc(row.evidence_uploaded_at)
    assert as_utc(row.evidence_expires_at) == as_utc(proof.submitted_at) + SEVEN_DAYS
    assert file.sha256_hash == row.evidence_sha256_hash
    assert len(stored_paths) == 2 and not stored_paths[0].exists() and stored_paths[1].exists()
    assert not stored_paths[1].with_suffix(".pending").exists()
    assert original == (previous.status, previous.decision_reason, previous.registered_values_json,
                        previous.extracted_values_json, previous.requested_section, as_utc(previous.reviewed_at))
    assert enrolled_state == (enrolled.status, enrolled.valid_until, as_utc(enrolled.confirmed_at))
    assert profile.section == "CURRENT" and user.account_status == "ACTIVE"
    audit = list(db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_resubmitted")))
    assert len(audit) == 1 and audit[0].metadata_json == {"status": "PENDING", "submission_version": row.submission_version}
    assert service.correction_evidence_status(row)["availability"] == "AVAILABLE"
    # A sequential replay cannot create another pending version.
    with pytest.raises(AppError) as caught:
        revise(db_session, returned_context)
    assert caught.value.code == "CHANGE_REQUEST_VERSION_CONFLICT"
    reviewer = ProfileChangeService(db_session).accounts.find_user_by_email("edit-super@example.edu")
    ProfileChangeService(db_session).return_request(reviewer, row.change_request_id,
        "Recheck the section.", submission_version=row.submission_version)
    assert not stored_paths[1].exists()


@pytest.mark.parametrize("failure", ["audit", "storage", "digest", "late_expiry", "database", "pending_guard"])
def test_failed_revision_rolls_back_rows_and_releases_new_bytes(
    db_session, returned_context, stored_paths, monkeypatch, failure,
):
    _, user, enrolled, profile, previous, _, _ = returned_context
    before = counts(db_session)
    record = AuditService.record
    store = CorScreeningService._store_cor_bytes
    screen = CorScreeningService.screen_correction_document
    if failure == "storage":
        def fail_store(self, content):
            if stored_paths:
                raise OSError("Injected storage failure")
            return store(self, content)
        monkeypatch.setattr(CorScreeningService, "_store_cor_bytes", fail_store)
    elif failure == "digest":
        def wrong_digest(self, *args, **kwargs):
            proof, _digest = screen(self, *args, **kwargs)
            return proof, b"x" * 32
        monkeypatch.setattr(CorScreeningService, "screen_correction_document", wrong_digest)
    else:
        def fail_audit(self, actor, event_type, *args, **kwargs):
            if event_type == "profile_change_resubmitted":
                if failure == "audit":
                    raise RuntimeError("Injected audit failure")
                if failure == "database":
                    raise OperationalError("PRIVATE SQL", {}, MysqlOperationalError(1213, "PRIVATE DRIVER"))
                if failure == "pending_guard":
                    raise IntegrityError("PRIVATE SQL", {}, MysqlIntegrityError(1062,
                        "Duplicate entry 'PRIVATE' for key 'profile_change_requests.uq_profile_change_requests_pending_student'"))
                from datetime import datetime
                import app.modules.profile_change.service as module
                deadline = db_session.scalar(select(ProfileChangeRequest.evidence_expires_at).where(
                    ProfileChangeRequest.status == "PENDING"))
                class Clock(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return as_utc(deadline)
                monkeypatch.setattr(module, "datetime", Clock)
            return record(self, actor, event_type, *args, **kwargs)
        monkeypatch.setattr(AuditService, "record", fail_audit)
    with pytest.raises((AppError, OSError, RuntimeError)) as caught:
        revise(db_session, returned_context)
    if failure in {"database", "pending_guard"}:
        assert caught.value.code == ("INTERNAL_ERROR" if failure == "database" else "CHANGE_REQUEST_PENDING")
        assert "PRIVATE" not in caught.value.message
    assert counts(db_session) == before
    db_session.refresh(previous)
    db_session.refresh(profile)
    assert previous.status == "RETURNED" and profile.section == "A"
    assert enrolled.status == "PASSED" and user.account_status == "ACTIVE"
    assert all(not path.exists() and not path.with_suffix(".pending").exists() for path in stored_paths)
