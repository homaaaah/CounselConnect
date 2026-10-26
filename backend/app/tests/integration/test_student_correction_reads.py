"""Student-owned correction reads through authenticated API boundaries."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_evidence_retention import advance
from .test_profile_change import _payload, _register, _superadmin, good_result, stub_screening


@pytest.fixture
def records(db_session, academic_references, monkeypatch):
    campus_id, program_id = academic_references
    stub_screening(monkeypatch, good_result())
    service = CorScreeningService(db_session)
    first, _screening = _register(service, email="first-read@example.edu")
    _scr, _user, profile, request = service.request_edit(first, _payload(campus_id, program_id, section="B"))
    result = good_result(student_no="20239999-B")
    result.fields.name = "Other Secret"
    stub_screening(monkeypatch, result)
    second, _screening = _register(service, email="second-read@example.edu")
    _scr, _user, _profile, other_request = service.request_edit(second, _payload(
        campus_id, program_id, student_number="20239999-B", first_name="Other", middle_name=None,
        last_name="Secret", section="OTHER-PRIVATE",
    ))
    return first, profile, request, second, other_request


def login(client, email="first-read@example.edu", password="password1"):
    response = client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert response.status_code == 200
    return response.json()


def test_student_list_and_detail_keep_current_requested_and_original_values_separate(db_client, records):
    first, _profile, request, _second, other_request = records
    login(db_client)
    listing = db_client.get("/api/v1/profile-change-requests")
    assert listing.status_code == 200
    assert listing.headers["cache-control"] == "no-store"
    assert listing.json()["total"] == 1
    item = listing.json()["items"][0]
    assert item["change_request"]["change_request_id"] == request.change_request_id
    assert item["change_request"]["change_request_id"] != other_request.change_request_id
    assert item["change_request"]["student_user_id"] == first.user_id
    assert item["change_request"]["status"] == "PENDING"
    assert item["change_request"]["submission_version"] == 1
    assert item["current_section"] == "A"
    assert item["change_request"]["requested_section"] == "B"
    assert item["registered_values_at_submission"]["section"] == "A"
    assert item["changed_fields"] == ["section"]
    assert item["change_request"]["created_at"].endswith("Z")
    detail = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "no-store"
    assert detail.json() == item


def test_other_student_id_is_concealed_and_query_cannot_override_owner(db_client, records):
    _first, _profile, request, second, other_request = records
    login(db_client)
    other = db_client.get(f"/api/v1/profile-change-requests/{other_request.change_request_id}")
    missing = db_client.get("/api/v1/profile-change-requests/999999999")
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()
    assert other.json()["error"]["code"] == "CHANGE_REQUEST_NOT_FOUND"
    forged = db_client.get(f"/api/v1/profile-change-requests?student_user_id={second.user_id}")
    assert [item["change_request"]["change_request_id"] for item in forged.json()["items"]] == [request.change_request_id]
    assert "OTHER-PRIVATE" not in forged.text


def test_student_response_has_only_permitted_fields_even_with_extra_snapshot_keys(db_session, db_client, records):
    _first, _profile, request, _second, _other = records
    request.registered_values_json = {**request.registered_values_json,
        "storage_key": "PRIVATE-STORAGE", "password_hash": "PRIVATE-HASH",
        "clinical_note": "PRIVATE-CLINICAL", "reviewed_by_user_id": 999,
    }
    request.reviewed_by_user_id = _superadmin(db_session).user_id
    db_session.commit()
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    data = response.json()
    assert set(data["registered_values_at_submission"]) == {"first_name", "middle_name", "last_name", "year_level", "section"}
    forbidden = {"reviewed_by_user_id", "pending_student_user_id", "evidence_file_id", "evidence_sha256_hash",
                 "evidence_expires_at", "evidence_uploaded_at", "extracted_values_json", "registered_values_json",
                 "storage_key", "password_hash", "clinical_note", "validation_results_json", "verification_token_hash"}

    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not forbidden & keys(data)
    for sentinel in ("PRIVATE-STORAGE", "PRIVATE-HASH", "PRIVATE-CLINICAL", "OTHER-PRIVATE"):
        assert sentinel not in response.text


@pytest.mark.parametrize("snapshot", [None, {"section": "A"}, {
    "first_name": "Juan", "middle_name": "Dela", "last_name": "Cruz",
    "year_level": "PRIVATE-INVALID", "section": "A",
}])
def test_unknown_or_incomplete_legacy_baseline_is_not_invented(db_session, db_client, records, snapshot, caplog):
    _first, _profile, request, _second, _other = records
    request.submission_version = None
    request.registered_values_json = snapshot
    db_session.commit()
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    item = response.json()
    assert item["change_request"]["submission_version"] is None
    assert item["registered_values_at_submission"] is None
    assert item["changed_fields"] is None
    assert item["current_section"] == "A"
    assert item["change_request"]["requested_section"] == "B"
    assert "PRIVATE-INVALID" not in response.text + caplog.text


def test_status_filter_and_sql_pagination_are_owner_scoped(db_session, db_client, records):
    first, _profile, request, _second, _other = records
    moment = datetime.now(timezone.utc) - timedelta(days=1)
    histories = []
    for status in ("APPROVED", "RETURNED", "REJECTED"):
        row = ProfileChangeRequest(student_user_id=first.user_id, cor_screening_id=request.cor_screening_id,
            status=status, requested_first_name="Juan", requested_middle_name="Dela", requested_last_name="Cruz",
            requested_year_level=1, requested_section="Historical", created_at=moment)
        db_session.add(row)
        histories.append(row)
    db_session.commit()
    login(db_client)
    pages = [db_client.get(f"/api/v1/profile-change-requests?page={page}&page_size=2").json() for page in (1, 2, 3)]
    assert [page["total"] for page in pages] == [4, 4, 4]
    assert [page["page"] for page in pages] == [1, 2, 3]
    assert pages[2]["items"] == []
    ids = [item["change_request"]["change_request_id"] for page in pages for item in page["items"]]
    assert ids == [request.change_request_id, *sorted([row.change_request_id for row in histories], reverse=True)]
    for status in ("PENDING", "APPROVED", "RETURNED", "REJECTED"):
        filtered = db_client.get(f"/api/v1/profile-change-requests?status={status}").json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["change_request"]["status"] == status


def test_another_owners_status_does_not_affect_filtered_total(db_session, db_client, records):
    _first, _profile, _request, _second, other = records
    other.status = "APPROVED"
    db_session.commit()
    login(db_client)
    response = db_client.get("/api/v1/profile-change-requests?status=APPROVED")
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


@pytest.mark.parametrize("status", ["PENDING_VERIFICATION", "VERIFICATION_EXPIRED"])
def test_restricted_students_can_read_account_status_without_unlocking_features(db_session, db_client, records, status):
    first, _profile, request, _second, _other = records
    first.account_status = status
    db_session.commit()
    login(db_client)
    assert db_client.get("/api/v1/profile-change-requests").status_code == 200
    assert db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}").status_code == 200
    assert db_client.get("/api/v1/appointments").status_code == 403
    assert first.account_status == status


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_STAFF"])
def test_staff_cannot_use_student_status_or_review_reads(db_session, db_client, records, role):
    _first, _profile, request, _second, _other = records
    user = User(email="staff-read@example.edu", password_hash=hash_password("password1"), role_code=role,
                account_status="ACTIVE", first_name="Staff", last_name="Reader")
    db_session.add(user)
    db_session.commit()
    login(db_client, user.email)
    for path in ("/api/v1/profile-change-requests", f"/api/v1/profile-change-requests/{request.change_request_id}"):
        response = db_client.get(path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_student_read_permission_does_not_grant_review_actions(db_client, records):
    _first, _profile, request, _second, _other = records
    auth = login(db_client)
    for action, body in (("approve", {"submission_version": 1}), ("reject", {"submission_version": 1, "reason": "Student cannot decide this request."})):
        response = db_client.post(f"/api/v1/profile-change-requests/{request.change_request_id}/{action}",
                                  json=body, headers={"X-CSRF-Token": auth["csrf_token"]})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"
    assert request.status == "PENDING"


def test_deactivated_student_is_denied_even_with_an_existing_session(db_session, db_client, records):
    first, _profile, request, _second, _other = records
    login(db_client)
    first.is_deactivated = True
    db_session.commit()
    for path in ("/api/v1/profile-change-requests", f"/api/v1/profile-change-requests/{request.change_request_id}"):
        response = db_client.get(path)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"


def test_anonymous_or_cor_token_only_reads_require_a_session(db_session, db_client, academic_references, monkeypatch):
    stub_screening(monkeypatch, good_result())
    _user, _screening, _, _, token = CorScreeningService(db_session).register_with_cor(
        "token-read@example.edu", "password1", b"%PDF-1.4 test", "cor.pdf")
    for headers in ({}, {"X-COR-Token": token}):
        for path in ("/api/v1/profile-change-requests", "/api/v1/profile-change-requests/1"):
            response = db_client.get(path, headers=headers)
            assert response.status_code == 401


@pytest.mark.parametrize("query", ["status=UNKNOWN", "page=0", "page_size=0", "page_size=101"])
def test_invalid_filters_and_page_bounds_return_safe_validation(db_client, records, query):
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_approved_and_returned_outcomes_are_readable_without_rewriting_history(db_session, db_client, records):
    _first, profile, request, _second, _other = records
    actor = _superadmin(db_session)
    ProfileChangeService(db_session).approve(actor, request.change_request_id, submission_version=1)
    audit_count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["change_request"]["status"] == "APPROVED"
    assert data["change_request"]["reviewed_at"].endswith("Z")
    assert data["current_section"] == profile.section == "B"
    assert data["registered_values_at_submission"]["section"] == "A"
    assert data["changed_fields"] == ["section"]
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count


def test_return_reason_is_visible_only_to_its_owner(db_session, db_client, records, monkeypatch):
    first, _profile, request, _second, _other = records
    advance(monkeypatch, 8)
    CorScreeningService(db_session).cleanup_due_files()
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    assert response.json()["change_request"]["status"] == "RETURNED"
    assert response.json()["change_request"]["decision_reason"] == "COR_EVIDENCE_EXPIRED"
    assert first.account_status == "ACTIVE"


def test_superadmin_queue_keeps_existing_shape(db_session, db_client, records):
    actor = _superadmin(db_session)
    login(db_client, actor.email, "super-pass-1")
    response = db_client.get("/api/v1/profile-change-requests?status=PENDING")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert "student" in response.json()["items"][0]
    assert "reviewed_by_user_id" in response.json()["items"][0]["change_request"]


def test_student_with_no_requests_gets_empty_own_envelope(db_session, db_client, records):
    _first, _profile, request, _second, _other = records
    empty = User(email="empty-read@example.edu", password_hash=hash_password("password1"), role_code="STUDENT",
                 account_status="PENDING_VERIFICATION", first_name="Empty", last_name="Student")
    db_session.add(empty)
    db_session.commit()
    login(db_client, empty.email)
    response = db_client.get("/api/v1/profile-change-requests")
    assert response.status_code == 200
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}
    assert db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}").status_code == 404


def test_missing_current_profile_does_not_fall_back_to_requested_values(db_session, db_client, records):
    _first, profile, request, _second, _other = records
    db_session.delete(profile)
    db_session.commit()
    login(db_client)
    response = db_client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")
    assert response.status_code == 200
    assert response.json()["current_year_level"] is None
    assert response.json()["current_section"] is None
    assert response.json()["change_request"]["requested_section"] == "B"


def test_status_read_endpoint_cannot_silently_rewrite_a_submitted_request(db_session, db_client, records):
    _first, _profile, request, second, _other = records
    auth = login(db_client)
    response = db_client.patch(f"/api/v1/profile-change-requests/{request.change_request_id}",
        json={"requested_section": "Silent rewrite", "student_user_id": second.user_id, "status": "APPROVED"},
        headers={"X-CSRF-Token": auth["csrf_token"]})
    assert response.status_code == 405
    db_session.refresh(request)
    assert request.status == "PENDING"
    assert request.requested_section == "B"
