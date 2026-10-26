"""Owner-bound, paginated correction lineage reads through the real API."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, func, select

from app.modules.audit.models import AuditEvent
from app.modules.profile_change.models import ProfileChangeRequest
from .test_profile_change import _superadmin
from .test_student_correction_reads import records, login  # noqa: F401


@pytest.fixture
def history(db_session, records):
    first, _, root, second, other = records
    actor = _superadmin(db_session)
    root.status = "RETURNED"
    root.reviewed_by_user_id = actor.user_id
    db_session.flush()
    rows = [root]
    stamp = datetime(2026, 10, 24, tzinfo=timezone.utc)
    for version in range(2, 25):
        row = ProfileChangeRequest(
            student_user_id=first.user_id, cor_screening_id=root.cor_screening_id,
            submission_version=version, previous_change_request_id=rows[-1].change_request_id,
            root_change_request_id=root.change_request_id,
            status="PENDING" if version == 24 else ("APPROVED" if version % 2 else "RETURNED"),
            requested_first_name="Juan", requested_middle_name="Dela", requested_last_name="Cruz",
            requested_year_level=1, requested_section="Version proposal", created_at=stamp,
            reviewed_at=stamp if version < 24 else None,
            reviewed_by_user_id=actor.user_id if version < 24 else None,
            decision_reason="Version decision" if version < 24 else None,
        )
        db_session.add(row)
        db_session.flush()
        rows.append(row)
    root.created_at = stamp
    # An unrelated same-owner root must never be grouped by owner alone.
    unrelated = ProfileChangeRequest(student_user_id=first.user_id, cor_screening_id=root.cor_screening_id,
        status="REJECTED", requested_first_name="Juan", requested_middle_name="Dela", requested_last_name="Cruz",
        requested_year_level=1, requested_section="UNRELATED-SECRET")
    db_session.add(unrelated)
    # FK constraints permit a corrupt cross-owner root reference. Reads still
    # apply the verified root's owner in SQL instead of trusting the link alone.
    foreign = ProfileChangeRequest(student_user_id=second.user_id, cor_screening_id=other.cor_screening_id,
        root_change_request_id=root.change_request_id, submission_version=999, status="REJECTED",
        requested_first_name="Foreign", requested_last_name="Secret", requested_year_level=1,
        requested_section="FOREIGN-SECRET")
    db_session.add(foreign)
    db_session.commit()
    return actor, first, root, rows, other, unrelated


@pytest.mark.parametrize("role", ["student", "superadmin"])
def test_lineage_pages_include_root_and_every_version_only_once(db_session, db_client, history, role):
    actor, first, root, rows, _, _ = history
    login(db_client, actor.email if role == "superadmin" else first.email,
          "super-pass-1" if role == "superadmin" else "password1")
    before = db_session.scalar(select(func.count()).select_from(AuditEvent))
    ids = []
    for page in (1, 2, 3):
        response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root.change_request_id}&page_size=10&page={page}")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["total"] == 24
        for item in response.json()["items"]:
            request = item["change_request"]
            ids.append(request["change_request_id"])
            assert request["student_user_id"] == first.user_id
            assert "submission_version" in request
            assert "previous_change_request_id" in request
            assert "root_change_request_id" in request
            assert ("reviewed_by_user_id" in request) == (role == "superadmin")
            assert request["created_at"].endswith("Z")
        assert "UNRELATED-SECRET" not in response.text
        assert "FOREIGN-SECRET" not in response.text
    assert ids == sorted([row.change_request_id for row in rows], reverse=True)
    empty = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root.change_request_id}&page=99").json()
    assert empty == {"items": [], "page": 99, "page_size": 20, "total": 24}
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == before


@pytest.mark.parametrize("role", ["student", "superadmin"])
@pytest.mark.parametrize("status", ["PENDING", "APPROVED", "RETURNED", "REJECTED"])
def test_history_status_counts_are_lineage_scoped(db_client, history, role, status):
    actor, first, root, rows, _, _ = history
    login(db_client, actor.email if role == "superadmin" else first.email,
          "super-pass-1" if role == "superadmin" else "password1")
    response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root.change_request_id}&status={status}&page_size=1")
    assert response.status_code == 200
    assert response.json()["total"] == sum(row.status == status for row in rows)
    assert len(response.json()["items"]) <= 1


def test_other_missing_and_nonroot_ids_are_concealed_before_paging(db_client, db_session, history, monkeypatch):
    _, first, root, rows, other, _ = history
    login(db_client, first.email)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid root reached history pagination")

    monkeypatch.setattr("app.modules.profile_change.repository.ProfileChangeRepository.page_requests", forbidden)
    responses = [db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root_id}")
                 for root_id in (other.change_request_id, 999999999, rows[1].change_request_id)]
    assert all(response.status_code == 404 for response in responses)
    assert responses[0].json() == responses[1].json() == responses[2].json()
    assert responses[0].json()["error"]["code"] == "CHANGE_REQUEST_NOT_FOUND"


@pytest.mark.parametrize("root_id", ["0", "-1", "nope", "18446744073709551616"])
def test_invalid_root_filter_is_safe_validation(db_client, history, root_id):
    _, first, _, _, _, _ = history
    login(db_client, first.email)
    response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root_id}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_history_uses_sql_count_limit_and_owner_predicate(db_session, db_client, history):
    actor, _, root, _, _, _ = history
    login(db_client, actor.email, "super-pass-1")
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if "FROM profile_change_requests" in statement:
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", record)
    try:
        response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root.change_request_id}&page_size=2")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", record)
    assert response.status_code == 200
    # The root may already be in the request session's identity map.
    pages = [statement for statement in statements if "count(" in statement.lower() or "LIMIT" in statement]
    assert len(pages) == 2
    assert "count(" in pages[0].lower()
    assert "student_user_id =" in pages[0] and "root_change_request_id =" in pages[0]
    assert "LIMIT" in pages[1]


@pytest.mark.parametrize("role", ["student", "superadmin"])
def test_deactivation_precedes_root_lookup(db_client, db_session, history, monkeypatch, role):
    actor, first, root, _, _, _ = history
    target = actor if role == "superadmin" else first
    login(db_client, target.email, "super-pass-1" if role == "superadmin" else "password1")
    target.is_deactivated = True
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Deactivated account reached root lookup")

    monkeypatch.setattr("app.modules.profile_change.service.ProfileChangeService._history_root", forbidden)
    response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={root.change_request_id}")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCOUNT_DEACTIVATED"


def test_legacy_root_is_singleton_without_invented_version(db_session, db_client, history):
    actor, _, _, _, _, legacy = history
    login(db_client, actor.email, "super-pass-1")
    response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={legacy.change_request_id}")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    request = response.json()["items"][0]["change_request"]
    assert request["submission_version"] is request["previous_change_request_id"] is request["root_change_request_id"] is None


def test_explicit_successor_of_legacy_root_preserves_unknown_older_version(db_session, db_client, history):
    actor, first, _, _, _, legacy = history
    child = ProfileChangeRequest(student_user_id=first.user_id, cor_screening_id=legacy.cor_screening_id,
        submission_version=1, root_change_request_id=legacy.change_request_id,
        previous_change_request_id=legacy.change_request_id, status="RETURNED",
        requested_first_name="Juan", requested_last_name="Cruz", requested_year_level=1, requested_section="B")
    db_session.add(child)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    response = db_client.get(f"/api/v1/profile-change-requests?root_change_request_id={legacy.change_request_id}")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    versions = {item["change_request"]["change_request_id"]: item["change_request"]["submission_version"]
                for item in response.json()["items"]}
    assert versions == {legacy.change_request_id: None, child.change_request_id: 1}
