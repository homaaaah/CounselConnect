"""Superadmin queue pagination, comparisons and purpose-bound read access."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, func, select

from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.profile_change.models import ProfileChangeRequest
from .test_profile_change import _superadmin
from .test_student_correction_reads import records, login  # noqa: F401


@pytest.fixture
def queue(db_session, db_client, records):
    first, _, request, _, other = records
    stamp = datetime(2026, 10, 24, tzinfo=timezone.utc)
    request.created_at = other.created_at = stamp
    rows = [request, other]
    for index in range(25):
        row = ProfileChangeRequest(
            student_user_id=first.user_id, cor_screening_id=request.cor_screening_id,
            status=("APPROVED", "RETURNED", "REJECTED")[index % 3],
            requested_first_name="Juan", requested_middle_name="Dela", requested_last_name="Cruz",
            requested_year_level=1, requested_section="History", created_at=stamp,
            reviewed_at=stamp, decision_reason="Historical decision",
        )
        db_session.add(row)
        rows.append(row)
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    return actor, rows


def test_queue_pages_are_complete_stable_and_sql_bounded(db_session, db_client, queue):
    _, rows = queue
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _many):
        if "FROM profile_change_requests" in statement and statement.lstrip().startswith("SELECT"):
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        first = db_client.get("/api/v1/profile-change-requests?page_size=10")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert first.status_code == 200
    assert len(statements) == 2
    assert any("count(" in statement.lower() for statement in statements)
    assert any("LIMIT" in statement and "ORDER BY" in statement for statement in statements)
    pages = [first] + [db_client.get(f"/api/v1/profile-change-requests?page_size=10&page={page}") for page in (2, 3)]
    ids = []
    for page, response in enumerate(pages, 1):
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert (body["page"], body["page_size"], body["total"]) == (page, 10, 27)
        ids.extend(item["change_request"]["change_request_id"] for item in body["items"])
    assert ids == sorted([row.change_request_id for row in rows], reverse=True)
    empty = db_client.get("/api/v1/profile-change-requests?page=99&page_size=10").json()
    assert empty == {"items": [], "page": 99, "page_size": 10, "total": 27}
    assert len(db_client.get("/api/v1/profile-change-requests").json()["items"]) == 20


@pytest.mark.parametrize("status", ["PENDING", "APPROVED", "RETURNED", "REJECTED"])
def test_status_filter_counts_and_paginates_before_projection(db_client, queue, status):
    _, rows = queue
    expected = sorted([row.change_request_id for row in rows if row.status == status], reverse=True)
    response = db_client.get(f"/api/v1/profile-change-requests?status={status}&page_size=2")
    assert response.status_code == 200
    assert response.json()["total"] == len(expected)
    assert [item["change_request"]["change_request_id"] for item in response.json()["items"]] == expected[:2]


def test_submission_timestamp_takes_precedence_over_id(db_session, db_client, queue):
    _, rows = queue
    rows[0].created_at = datetime(2026, 10, 25, tzinfo=timezone.utc)
    db_session.commit()
    response = db_client.get("/api/v1/profile-change-requests?page_size=1")
    assert response.status_code == 200
    assert response.json()["items"][0]["change_request"]["change_request_id"] == rows[0].change_request_id


@pytest.mark.parametrize("query", ["status=UNKNOWN", "page=0", "page_size=0", "page_size=101"])
def test_invalid_queue_filters_use_safe_validation(db_client, queue, query):
    response = db_client.get(f"/api/v1/profile-change-requests?{query}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_queue_comparisons_use_immutable_allowlisted_baseline_and_do_not_write(
    db_session, db_client, records,
):
    first, _, request, _, _ = records
    request.registered_values_json = {**request.registered_values_json, "clinical_note": "PRIVATE-CLINICAL",
        "storage_key": "PRIVATE-STORAGE", "token": "PRIVATE-TOKEN"}
    first.first_name = "Current"
    request.requested_first_name = "  JUAN  "
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    before = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = db_client.get("/api/v1/profile-change-requests?status=PENDING")
    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["change_request"]["change_request_id"] == request.change_request_id)
    assert item["changed_fields"] == ["section"]
    assert item["current_first_name"] == "Current"
    assert item["change_request"]["created_at"].endswith("Z")
    assert set(item) == {"change_request", "student", "current_first_name", "current_middle_name",
                         "current_last_name", "current_year_level", "current_section", "changed_fields"}
    for secret in ("PRIVATE-CLINICAL", "PRIVATE-STORAGE", "PRIVATE-TOKEN", "password_hash", "evidence_sha256_hash", "registered_values_json"):
        assert secret not in response.text
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == before
    db_session.refresh(request)
    assert request.status == "PENDING"
    assert request.registered_values_json["first_name"] == "Juan"


@pytest.mark.parametrize("snapshot", [None, {"section": "A"}, {"first_name": [], "middle_name": None,
    "last_name": "Cruz", "year_level": 1, "section": "A"}])
def test_queue_unknown_legacy_comparison_stays_null(db_session, db_client, records, snapshot):
    _, _, request, _, _ = records
    request.registered_values_json = snapshot
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    items = db_client.get("/api/v1/profile-change-requests").json()["items"]
    item = next(item for item in items if item["change_request"]["change_request_id"] == request.change_request_id)
    assert item["changed_fields"] is None


def test_deactivated_superadmin_is_denied_before_queue_query(db_session, db_client, queue, monkeypatch):
    actor, _ = queue
    actor.is_deactivated = True
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized queue query")

    monkeypatch.setattr("app.modules.profile_change.repository.ProfileChangeRepository.page_requests", forbidden)
    response = db_client.get("/api/v1/profile-change-requests")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_shared_guard_also_denies_deactivated_superadmin_decisions(db_session, db_client, queue, monkeypatch, action):
    actor, rows = queue
    csrf = db_client.get("/api/v1/auth/csrf").json()["csrf_token"]
    actor.is_deactivated = True
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Unauthorized decision reached request lock")

    monkeypatch.setattr("app.modules.profile_change.service.ProfileChangeService._lock_request_after_student", forbidden)
    response = db_client.post(f"/api/v1/profile-change-requests/{rows[0].change_request_id}/{action}",
                              headers={"X-CSRF-Token": csrf}, json={"submission_version": 1} if action == "approve" else {"submission_version": 1, "reason": "Return for revision"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"
    db_session.refresh(rows[0])
    assert rows[0].status == "PENDING"


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_STAFF"])
def test_other_staff_cannot_read_queue(db_session, db_client, records, role):
    actor = User(email="queue-staff@example.edu", password_hash=hash_password("password1"),
                 role_code=role, account_status="ACTIVE", first_name="Staff", last_name="Member")
    db_session.add(actor)
    db_session.commit()
    login(db_client, actor.email)
    response = db_client.get("/api/v1/profile-change-requests")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


def test_missing_current_profile_does_not_remove_queue_record(db_session, db_client, queue, records):
    first, profile, request, _, _ = records
    db_session.delete(profile)
    db_session.commit()
    response = db_client.get("/api/v1/profile-change-requests?status=PENDING")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    item = next(item for item in response.json()["items"] if item["student"]["user_id"] == first.user_id)
    assert item["change_request"]["change_request_id"] == request.change_request_id
    assert item["current_year_level"] is item["current_section"] is None


def test_queue_empty_and_anonymous_or_token_only_denied(db_session, db_client):
    assert db_client.get("/api/v1/profile-change-requests").status_code == 401
    assert db_client.get("/api/v1/profile-change-requests", headers={"X-COR-Token": "not-a-session"}).status_code == 401
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    response = db_client.get("/api/v1/profile-change-requests")
    assert response.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}
