"""Full correction lifecycle through real routes with stubbed document tooling."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import select

from app.modules.accounts.models import StudentProfile, User
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService, SEVEN_DAYS, as_utc
from app.modules.profile_change.models import ProfileChangeRequest
from .test_profile_change import good_result, stub_screening, _payload, _superadmin
from .test_student_correction_reads import login
from .test_correction_approval_version import csrf
from .test_correction_resubmission_api import post, parts
from .test_correction_evidence_retention import advance


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("ending", ["approve", "expire", "return_again"])
def test_complete_return_revision_review_lifecycle(db_session, db_client, academic_references, monkeypatch, legacy, ending):
    stub_screening(monkeypatch, good_result())
    email = "lifecycle@example.edu"
    registration = db_client.post("/api/v1/accounts/register/student-with-cor",
        data={"email": email, "password": "password1"},
        files={"file": ("registration.pdf", b"%PDF-1.4 original registration", "application/pdf")})
    assert registration.status_code == 201
    assert registration.headers["cache-control"] == "no-store"
    initial = db_client.post("/api/v1/cor-screenings/request-edit",
        headers={"X-COR-Token": registration.json()["verification_token"]},
        json=_payload(*academic_references, section="B").model_dump())
    assert initial.status_code == 200
    root_id = initial.json()["change_request"]["change_request_id"]
    root = db_session.get(ProfileChangeRequest, root_id)
    student = db_session.get(User, root.student_user_id)
    enrolled = db_session.get(CorScreening, root.registered_cor_screening_id)
    profile = db_session.get(StudentProfile, student.user_id)
    original_enrollment = enrolled.cor_screening_id, enrolled.status, enrolled.valid_until, as_utc(enrolled.confirmed_at)
    service = CorScreeningService(db_session)
    old_file = db_session.get(CorScreeningFile, root.evidence_file_id)
    old_path = Path(service._storage_path(old_file.storage_key))
    assert old_path.exists() and student.account_status == "ACTIVE" and profile.section == "A"
    reviewer = _superadmin(db_session)
    if legacy:
        # Only the legacy precondition is synthetic: do not invent missing history.
        root.submission_version = None
        root.registered_values_json = root.extracted_values_json = None
    db_session.commit()
    old_snapshots = deepcopy((root.registered_values_json, root.extracted_values_json))
    login(db_client, email)
    assert db_client.get(f"/api/v1/profile-change-requests/{root_id}").json()["can_resubmit"] is False
    login(db_client, reviewer.email, "super-pass-1")
    returned = db_client.post(f"/api/v1/profile-change-requests/{root_id}/return", headers=csrf(db_client),
        json={"submission_version": None if legacy else 1, "reason": "Check name, year and section."})
    assert returned.status_code == 200 and returned.headers["cache-control"] == "no-store"
    assert not old_path.exists()
    assert db_session.get(CorScreeningFile, old_file.cor_screening_file_id) is None
    fresh = good_result()
    fresh.fields.name = "Juana Cruz"
    fresh.fields.year = "2"
    fresh.fields.section = "B"
    stub_screening(monkeypatch, fresh)
    proposal = json.dumps({"first_name": "Juana", "middle_name": None, "year_level": 2, "section": "B"})
    selected = root
    new_ids = []
    for iteration in range(2 if ending == "return_again" else 1):
        login(db_client, email)
        detail = db_client.get(f"/api/v1/profile-change-requests/{selected.change_request_id}")
        assert detail.json()["can_resubmit"] is True
        upload = parts("null" if selected.submission_version is None else str(selected.submission_version), proposal)
        content = f"%PDF-1.4 fresh lifecycle {iteration}".encode()
        upload[-1] = ("file", ("fresh.pdf", content, "application/pdf"))
        result = post(db_client, selected, upload)
        assert result.status_code == 201 and result.headers["cache-control"] == "no-store"
        assert result.json()["can_resubmit"] is False
        assert result.json()["current_section"] == "A"
        new_id = result.json()["change_request"]["change_request_id"]
        new_ids.append(new_id)
        selected = db_session.get(ProfileChangeRequest, new_id)
        proof = db_session.get(CorScreening, selected.cor_screening_id)
        file = db_session.get(CorScreeningFile, selected.evidence_file_id)
        path = Path(service._storage_path(file.storage_key))
        assert selected.root_change_request_id == root_id
        assert selected.submission_version == iteration + (1 if legacy else 2)
        assert selected.registered_values_json["section"] == "A"
        assert selected.extracted_values_json["section"] == "B"
        assert as_utc(selected.evidence_expires_at) == as_utc(file.uploaded_at) + SEVEN_DAYS
        deadline = selected.evidence_expires_at
        assert proof.purpose == "CORRECTION" and proof.confirmed_at is proof.valid_until is proof.verification_token_hash is None
        login(db_client, reviewer.email, "super-pass-1")
        preview = db_client.get(f"/api/v1/profile-change-requests/{new_id}/cor")
        assert preview.status_code == 200 and preview.content == content
        assert preview.headers["cache-control"] == "no-store"
        review = db_client.get(f"/api/v1/profile-change-requests/{new_id}").json()
        assert review["evidence"]["availability"] == "AVAILABLE"
        assert review["registered_values_at_submission"]["section"] == "A"
        assert review["extracted_values"]["section"] == "B"
        if ending == "return_again" and iteration == 0:
            result = db_client.post(f"/api/v1/profile-change-requests/{new_id}/return", headers=csrf(db_client),
                json={"submission_version": selected.submission_version, "reason": "Upload the corrected current copy."})
            assert result.status_code == 200 and not path.exists()
    if ending == "expire":
        advance(monkeypatch, 8)
        service.cleanup_due_files()
        db_session.refresh(selected)
        assert selected.status == "RETURNED" and selected.decision_reason == "COR_EVIDENCE_EXPIRED"
    else:
        approved = db_client.post(f"/api/v1/profile-change-requests/{selected.change_request_id}/approve",
            headers=csrf(db_client), json={"submission_version": selected.submission_version})
        assert approved.status_code == 200 and approved.headers["cache-control"] == "no-store"
        assert approved.json()["evidence"]["availability"] == "RESOLVED"
        assert approved.json()["current_registered_values"]["section"] == "B"
        repeated = db_client.post(f"/api/v1/profile-change-requests/{selected.change_request_id}/approve",
            headers=csrf(db_client), json={"submission_version": selected.submission_version})
        assert repeated.status_code == 409
        assert (student.first_name, student.middle_name, profile.year_level, profile.section) == ("Juana", None, 2, "B")
    assert not path.exists() and db_session.get(CorScreeningFile, file.cor_screening_file_id) is None
    assert as_utc(selected.evidence_expires_at) == as_utc(deadline)
    assert old_snapshots == (root.registered_values_json, root.extracted_values_json)
    assert original_enrollment == (enrolled.cor_screening_id, enrolled.status, enrolled.valid_until, as_utc(enrolled.confirmed_at))
    assert student.account_status == "ACTIVE" and enrolled.extracted_first_name == "Juan"
    login(db_client, email)
    outcome = db_client.get(f"/api/v1/profile-change-requests/{selected.change_request_id}")
    assert outcome.json()["can_resubmit"] is (ending == "expire")
    assert outcome.json()["change_request"]["status"] == ("RETURNED" if ending == "expire" else "APPROVED")
    assert "reviewed_by_user_id" not in outcome.text and "storage_key" not in outcome.text
    history = db_client.get("/api/v1/profile-change-requests", params={"root_change_request_id": root_id}).json()
    assert history["total"] == len(new_ids) + 1
    assert {item["change_request"]["change_request_id"] for item in history["items"]} == {root_id, *new_ids}
    audits = list(db_session.scalars(select(AuditEvent).where(AuditEvent.event_type == "profile_change_resubmitted",
        AuditEvent.actor_user_id == student.user_id)))
    assert len(audits) == len(new_ids)
    assert all(set(audit.metadata_json) == {"status", "submission_version"} for audit in audits)
