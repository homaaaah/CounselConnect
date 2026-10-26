"""Scratch COR processing never creates enrollment, correction or evidence rows."""

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select

from app.core.exceptions import AppError
from app.modules.accounts.models import Campus, Program
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening import screening as engine
from app.modules.cor_screening.models import CorScreening
from .test_correction_resubmission_preflight import returned_context  # noqa: F401
from .test_profile_change import good_result, stub_screening


def process(values, content=b"%PDF-1.4 fresh", filename="fresh.pdf"):
    service, user, enrolled, *_ = values
    return service.screen_correction_document(user, registered_cor_screening_id=enrolled.cor_screening_id,
                                             content=content, filename=filename)


@pytest.fixture
def scratch(returned_context, monkeypatch):
    service = returned_context[0]
    paths = []
    store = service._store_cor_bytes
    def capture(content):
        key = store(content)
        paths.append(Path(service._storage_path(key)))
        return key
    monkeypatch.setattr(service, "_store_cor_bytes", capture)
    return returned_context, paths


@pytest.mark.parametrize("unmapped", [False, True])
def test_passing_document_returns_only_transient_proof_and_bound_digest(db_session, scratch, monkeypatch, unmapped):
    values, paths = scratch
    service, user, enrolled, profile, row, _, _ = values
    result = good_result()
    if unmapped:
        result.fields.campus = "Unmapped campus"
        result.fields.course = "Unmapped program"
        result.fields.academic_period = ""
    stub_screening(monkeypatch, result)
    count = db_session.scalar(select(func.count()).select_from(CorScreening))
    audits = db_session.scalar(select(func.count()).select_from(AuditEvent))
    original = enrolled.valid_until, enrolled.confirmed_at, row.status, row.registered_values_json.copy()
    monkeypatch.setattr(db_session, "commit", lambda: pytest.fail("scratch processing must not commit"))
    proof, digest = process(values)
    assert inspect(proof).transient
    assert proof.purpose == "CORRECTION" and proof.status == "PASSED"
    assert proof.cor_screening_id is None and proof.confirmed_at is None and proof.valid_until is None
    assert proof.verification_token_hash is None
    assert digest == hashlib.sha256(b"%PDF-1.4 fresh").digest()
    assert proof.submitted_at <= proof.processed_at
    assert len(paths) == 1 and not paths[0].exists() and not paths[0].with_suffix(".pending").exists()
    assert original == (enrolled.valid_until, enrolled.confirmed_at, row.status, row.registered_values_json)
    assert user.account_status == "ACTIVE" and profile.section == "A"
    assert not db_session.new and not db_session.dirty
    assert db_session.scalar(select(func.count()).select_from(CorScreening)) == count
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == audits


@pytest.mark.parametrize("case,code", [
    ("number", "COR_CONTEXT_MISMATCH"), ("period", "COR_CONTEXT_MISMATCH"),
    ("campus", "COR_CONTEXT_MISMATCH"), ("program", "COR_CONTEXT_MISMATCH"),
    ("barcode", "COR_SCREENING_FAILED"), ("unreadable", "COR_SCREENING_FAILED"),
    ("missing_name", "SCREENING_NOT_CONFIRMABLE"), ("missing_year", "SCREENING_NOT_CONFIRMABLE"),
    ("unavailable", "SCREENING_UNAVAILABLE"), ("unexpected", None),
])
def test_failed_or_mismatched_screening_discards_scratch_and_preserves_history(
    db_session, scratch, monkeypatch, case, code,
):
    values, paths = scratch
    service, user, enrolled, profile, row, _, _ = values
    result = good_result()
    if case == "number":
        result.fields.student_no = "20239999-B"
    elif case == "period":
        result.fields.academic_period = "2099-2100"
    elif case == "campus":
        db_session.add(Campus(campus_name="Different mapped campus"))
        db_session.commit()
        result.fields.campus = "Different mapped campus"
    elif case == "program":
        current = service.accounts.find_program(profile.program_id)
        db_session.add(Program(department_id=current.department_id, program_code="FRESH-ALT", program_name="Different mapped program"))
        db_session.commit()
        result.fields.course = "Different mapped program"
    elif case == "barcode":
        result.barcode_status = engine.BARCODE_MISMATCH
    elif case == "unreadable":
        result.method = "none"
    elif case == "missing_name":
        result.fields.name = ""
    elif case == "missing_year":
        result.fields.year = ""
    stub_screening(monkeypatch, result)
    if case in {"unavailable", "unexpected"}:
        def fail(*args):
            raise (engine.ScreeningUnavailableError("PRIVATE") if case == "unavailable" else RuntimeError("Injected"))
        monkeypatch.setattr(engine, "screen_pdf", fail)
    with pytest.raises(AppError if code else RuntimeError) as caught:
        process(values)
    if code:
        assert caught.value.code == code
        assert "PRIVATE" not in caught.value.message
    assert paths and not paths[0].exists() and not paths[0].with_suffix(".pending").exists()
    assert row.status == "RETURNED" and profile.section == "A"
    assert enrolled.status == "PASSED" and user.account_status == "ACTIVE"
    assert not db_session.new and not db_session.dirty


@pytest.mark.parametrize("content,filename,code", [
    (b"invalid", "cor.pdf", "COR_INVALID_PDF"), (b"%PDF-1.4", "cor.txt", "COR_MUST_BE_PDF"),
])
def test_invalid_pdf_is_rejected_before_scratch_storage(scratch, content, filename, code):
    values, paths = scratch
    with pytest.raises(AppError) as caught:
        process(values, content, filename)
    assert caught.value.code == code
    assert paths == []


def test_failed_scratch_deletion_keeps_marker_for_existing_cleanup(scratch, monkeypatch, caplog):
    values, paths = scratch
    service = values[0]
    delete = service._delete_cor_bytes
    monkeypatch.setattr(service, "_delete_cor_bytes", lambda key: False)
    process(values)
    assert paths[0].exists() and paths[0].with_suffix(".pending").exists()
    assert str(paths[0]) not in caplog.text
    assert "cor_screening_upload_cleanup_retry_required" in caplog.text
    # Release only this test's scratch file; no application storage sweep.
    assert delete(f"cor/{paths[0].name}")


@pytest.mark.parametrize("case,code", [("deactivated", "ACCOUNT_DEACTIVATED"),
    ("expired_account", "CORRECTION_RESUBMISSION_NOT_ALLOWED"), ("role", "FORBIDDEN_ROLE"),
    ("dependencies", "SCREENING_UNAVAILABLE")])
def test_ineligible_actor_or_missing_dependencies_never_stores_scratch(db_session, scratch, monkeypatch, case, code):
    values, paths = scratch
    user = values[1]
    if case == "deactivated":
        user.is_deactivated = True
    elif case == "expired_account":
        user.account_status = "VERIFICATION_EXPIRED"
    elif case == "role":
        user.role_code = "COUNSELOR"
    else:
        def fail(*args):
            raise engine.ScreeningUnavailableError("PRIVATE")
        monkeypatch.setattr(engine, "ensure_dependencies", fail)
    db_session.commit()
    with pytest.raises(AppError) as caught:
        process(values)
    assert caught.value.code == code
    assert paths == []
