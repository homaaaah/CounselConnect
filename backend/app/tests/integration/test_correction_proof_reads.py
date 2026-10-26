"""Separate correction evidence reads preserve the current enrolled baseline."""

from datetime import timedelta

import pytest

from app.modules.accounts.models import Campus, Program
from .test_correction_cleanup_isolation import separate_proof
from .test_correction_private_cor import preview
from .test_profile_change import _superadmin
from .test_student_correction_reads import login


@pytest.fixture
def proof_context(db_session, academic_references, monkeypatch):
    values = separate_proof(db_session, academic_references, monkeypatch)
    service, user, enrolled, profile, request, file, path, proof = values
    proof.extracted_student_number = enrolled.extracted_student_number
    proof.extracted_campus_id = enrolled.extracted_campus_id
    proof.extracted_program_id = enrolled.extracted_program_id
    proof.extracted_academic_period = enrolled.extracted_academic_period
    db_session.commit()
    return values


@pytest.mark.parametrize("unmapped", [False, True])
def test_separate_proof_preview_and_detail_are_safe_read_only(db_session, db_client, proof_context, unmapped):
    service, user, enrolled, profile, request, file, path, proof = proof_context
    if unmapped:
        proof.extracted_campus_id = None
        proof.extracted_program_id = None
        proof.extracted_academic_period = None
        db_session.commit()
    validity = enrolled.valid_until
    actor = _superadmin(db_session)
    login(db_client, actor.email, "super-pass-1")
    result = preview(db_client, request)
    assert result.status_code == 200
    assert result.content == path.read_bytes()
    assert result.headers["cache-control"] == "no-store"
    detail = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert detail.status_code == 200
    assert detail.json()["evidence"]["availability"] == "AVAILABLE"
    assert proof.confirmed_at is None and proof.valid_until is None
    assert enrolled.status == "PASSED" and enrolled.valid_until == validity
    assert user.account_status == "ACTIVE" and profile.section == "A"
    assert request.status == "PENDING"
    assert not db_session.dirty


@pytest.mark.parametrize("case", [
    "missing_number", "number", "campus", "program", "period", "baseline",
    "failed", "unconfirmed_pass", "granted_validity", "inactive", "deactivated", "expired",
    "inactive_campus", "inactive_program", "profile_number",
])
def test_separate_proof_context_mismatch_is_unavailable(db_session, proof_context, case):
    service, user, enrolled, profile, request, file, path, proof = proof_context
    if case == "missing_number":
        proof.extracted_student_number = None
    elif case == "number":
        proof.extracted_student_number = "20239999-B"
    elif case == "campus":
        other = Campus(campus_name="Other proof campus")
        db_session.add(other)
        db_session.flush()
        proof.extracted_campus_id = other.campus_id
    elif case == "program":
        current = service.accounts.find_program(profile.program_id)
        other = Program(department_id=current.department_id, program_code="OTHER-PROOF", program_name="Other proof program")
        db_session.add(other)
        db_session.flush()
        proof.extracted_program_id = other.program_id
    elif case == "period":
        proof.extracted_academic_period = "2099-2100"
    elif case == "baseline":
        request.registered_cor_screening_id = proof.cor_screening_id
    elif case == "failed":
        proof.status = "FAILED"
    elif case == "unconfirmed_pass":
        proof.confirmed_at = enrolled.confirmed_at
    elif case == "granted_validity":
        proof.valid_until = enrolled.valid_until
    elif case == "inactive":
        user.account_status = "VERIFICATION_EXPIRED"
    elif case == "deactivated":
        user.is_deactivated = True
    elif case == "inactive_campus":
        service.accounts.find_campus(profile.campus_id).is_active = False
    elif case == "inactive_program":
        service.accounts.find_program(profile.program_id).is_active = False
    elif case == "profile_number":
        profile.student_number = "20239999-B"
    else:
        enrolled.valid_until -= timedelta(days=400)
    db_session.commit()
    status, content = service.inspect_correction_evidence(request)
    assert status["availability"] == "UNAVAILABLE"
    assert content is None
    assert path.exists()
    assert request.status == "PENDING" and profile.section == "A"
