"""Safe structured review detail, immutable context and bounded owner history."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening
from .test_profile_change import _superadmin
from .test_student_correction_reads import records, login  # noqa: F401
from .test_correction_history_reads import history  # noqa: F401


@pytest.fixture
def reviewer(db_session, db_client, records):
    actor = _superadmin(db_session)
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    return actor


def detail(client, request):
    return client.get(f"/api/v1/profile-change-requests/{request.change_request_id}")


def test_detail_separates_current_extracted_baseline_and_proposal(db_session, db_client, records, reviewer):
    first, profile, request, _, _ = records
    extraction = {**request.extracted_values_json, "middle_name": None, "section": " A\t  "}
    request.extracted_values_json = extraction
    first.first_name = "Current name"
    profile.section = "Current section"
    db_session.commit()
    count = db_session.scalar(select(func.count()).select_from(AuditEvent))
    response = detail(db_client, request)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["student"]["user_id"] == first.user_id
    assert body["extracted_values"] == extraction
    assert body["registered_values_at_submission"]["first_name"] == "Juan"
    assert body["registered_values_at_submission"]["section"] == "A"
    assert body["current_registered_values"]["first_name"] == "Current name"
    assert body["current_registered_values"]["section"] == "Current section"
    assert body["current_registered_values"]["student_number"] == "20231234-A"
    assert body["proposed_changes"] == {"section": "B"}
    assert body["changed_fields"] == ["section"]
    assert body["can_resubmit"] is False
    assert body["evidence"]["availability"] == "AVAILABLE"
    assert len(body["history"]) == 1
    assert body["history"][0]["change_request_id"] == request.change_request_id
    assert body["change_request"]["created_at"].endswith("Z")
    assert db_session.scalar(select(func.count()).select_from(AuditEvent)) == count
    db_session.refresh(request)
    assert request.status == "PENDING" and request.extracted_values_json == extraction
    assert first.first_name == "Current name" and profile.section == "Current section"


def test_snapshot_projection_excludes_arbitrary_private_json(db_session, db_client, records, reviewer, caplog):
    _, _, request, _, _ = records
    secret = {"storage_key": "PRIVATE-PATH", "token": "PRIVATE-TOKEN",
              "clinical_note": "PRIVATE-CLINICAL", "nested": {"raw_ocr": "PRIVATE-OCR"}}
    request.extracted_values_json = {**request.extracted_values_json, **secret}
    request.registered_values_json = {**request.registered_values_json, **secret}
    db_session.commit()
    response = detail(db_client, request)
    assert response.status_code == 200
    for forbidden in (*secret.keys(), *[v for v in secret.values() if isinstance(v, str)], "PRIVATE-OCR",
                      "evidence_file_id", "evidence_sha256_hash", "verification_token_hash", "validation_results_json"):
        assert forbidden not in response.text + caplog.text
    assert set(response.json()["extracted_values"]) == {"student_number", "first_name", "middle_name", "last_name",
        "campus_id", "program_id", "year_level", "section", "academic_period", "valid_until"}


@pytest.mark.parametrize("snapshot", [None, {"section": "A"}, {"first_name": {"secret": "PRIVATE-INVALID"}}, "PRIVATE-INVALID"])
def test_unknown_snapshots_are_not_reconstructed(db_session, db_client, records, reviewer, snapshot, caplog):
    _, _, request, _, _ = records
    request.extracted_values_json = snapshot
    request.registered_values_json = snapshot
    request.submission_version = None
    db_session.commit()
    response = detail(db_client, request)
    assert response.status_code == 200
    body = response.json()
    assert body["extracted_values"] is body["registered_values_at_submission"] is body["changed_fields"] is None
    assert body["change_request"]["submission_version"] is None
    assert set(body["proposed_changes"]) == {"first_name", "middle_name", "last_name", "year_level", "section"}
    assert "PRIVATE-INVALID" not in response.text + caplog.text


@pytest.mark.parametrize("field,value", [("year_level", "PRIVATE-INVALID"), ("valid_until", "PRIVATE-INVALID"),
                                       ("valid_until", 0), ("valid_until", "0"),
                                       ("student_number", {"secret": "PRIVATE-INVALID"})])
def test_complete_but_invalid_snapshot_is_unknown(db_session, db_client, records, reviewer, field, value, caplog):
    _, _, request, _, _ = records
    request.registered_values_json = {**request.registered_values_json, field: value}
    db_session.commit()
    response = detail(db_client, request)
    assert response.status_code == 200
    assert response.json()["registered_values_at_submission"] is None
    assert response.json()["changed_fields"] is None
    assert "PRIVATE-INVALID" not in response.text + caplog.text


def test_middle_name_removal_is_explicit_null_proposal(db_session, db_client, records, reviewer):
    _, _, request, _, _ = records
    request.requested_middle_name = None
    db_session.commit()
    body = detail(db_client, request).json()
    assert body["proposed_changes"] == {"middle_name": None, "section": "B"}
    assert body["changed_fields"] == ["middle_name", "section"]


def test_missing_current_profile_remains_unknown(db_session, db_client, records, reviewer):
    _, profile, request, _, _ = records
    db_session.delete(profile)
    db_session.commit()
    response = detail(db_client, request)
    assert response.status_code == 200
    values = response.json()["current_registered_values"]
    for key in ("student_number", "campus_id", "program_id", "year_level", "section"):
        assert values[key] is None
    assert values["first_name"] == "Juan"


def test_inline_history_is_only_selected_and_immediate_predecessor(db_client, history):
    actor, _, _, rows, _, _ = history
    login(db_client, actor.email, "super-pass-1")
    response = detail(db_client, rows[-1])
    assert response.status_code == 200
    entries = response.json()["history"]
    assert [entry["change_request_id"] for entry in entries] == [rows[-1].change_request_id, rows[-2].change_request_id]
    assert entries[1]["reviewed_by_user_id"] == actor.user_id
    assert entries[1]["reviewed_at"].endswith("Z")
    assert "FOREIGN-SECRET" not in response.text and "UNRELATED-SECRET" not in response.text


@pytest.mark.parametrize("link", ["foreign_previous", "unrelated_previous", "foreign_root"])
def test_invalid_history_links_never_expand_scope(db_session, db_client, history, link):
    actor, _, _, rows, foreign, unrelated = history
    request = rows[-1]
    if link == "foreign_root":
        request.root_change_request_id = foreign.change_request_id
    else:
        request.previous_change_request_id = (foreign if link == "foreign_previous" else unrelated).change_request_id
    db_session.commit()
    login(db_client, actor.email, "super-pass-1")
    response = detail(db_client, request)
    assert response.status_code == 200
    body = response.json()
    assert len(body["history"]) == 1
    assert body["change_request"]["previous_change_request_id"] is None
    if link == "foreign_root":
        assert body["change_request"]["root_change_request_id"] is None
    assert "OTHER-PRIVATE" not in response.text and "UNRELATED-SECRET" not in response.text


@pytest.mark.parametrize("status", ["APPROVED", "RETURNED", "REJECTED"])
def test_terminal_detail_survives_deleted_evidence(db_session, db_client, records, reviewer, status):
    _, _, request, _, _ = records
    request.status = status
    request.reviewed_by_user_id = reviewer.user_id
    request.reviewed_at = datetime.now(timezone.utc)
    request.decision_reason = "Recorded outcome"
    request.evidence_file_id = None
    db_session.commit()
    response = detail(db_client, request)
    assert response.status_code == 200
    assert response.json()["change_request"]["status"] == status
    assert response.json()["history"][0]["decision_reason"] == "Recorded outcome"
    assert response.json()["registered_values_at_submission"]["section"] == "A"


def test_current_enrollment_ignores_unconfirmed_and_correction_only_screenings(db_session, db_client, records, reviewer):
    first, _, request, _, _ = records
    registered = db_session.get(CorScreening, request.cor_screening_id)
    period, expiry = registered.extracted_academic_period, registered.valid_until.isoformat()
    now = datetime.now(timezone.utc)
    for purpose, status, confirmed in [("REGISTRATION", "AWAITING_CONFIRMATION", None), ("CORRECTION", "PASSED", now)]:
        db_session.add(CorScreening(student_user_id=first.user_id, status=status, purpose=purpose,
            format_template_version="test", barcode_status="DECODED", submitted_at=now,
            confirmed_at=confirmed, extracted_academic_period="WRONG-CONTEXT", valid_until=(now + timedelta(days=999)).date()))
    db_session.commit()
    current = detail(db_client, request).json()["current_registered_values"]
    assert current["academic_period"] == period and current["valid_until"] == expiry
    newer = CorScreening(student_user_id=first.user_id, status="PASSED", purpose="REGISTRATION",
        format_template_version="test", barcode_status="DECODED", submitted_at=now,
        confirmed_at=now + timedelta(seconds=1), extracted_academic_period="NEW-REGISTERED-PERIOD",
        valid_until=(now + timedelta(days=100)).date())
    db_session.add(newer)
    db_session.commit()
    current = detail(db_client, request).json()["current_registered_values"]
    assert current["academic_period"] == "NEW-REGISTERED-PERIOD"
    assert current["valid_until"] == newer.valid_until.isoformat()


def test_no_registered_enrollment_does_not_fall_back_to_snapshot(db_session, db_client, records, reviewer):
    _, _, request, _, _ = records
    screening = db_session.get(CorScreening, request.cor_screening_id)
    screening.confirmed_at = None
    db_session.commit()
    current = detail(db_client, request).json()["current_registered_values"]
    assert current["academic_period"] is current["valid_until"] is None


def test_student_detail_keeps_existing_narrow_shape(db_client, records):
    _, _, request, _, _ = records
    login(db_client)
    response = detail(db_client, request)
    assert response.status_code == 200
    for key in ("student", "extracted_values", "history", "current_registered_values", "proposed_changes", "reviewed_by_user_id"):
        assert key not in response.json() and key not in response.json()["change_request"]


@pytest.mark.parametrize("field,value,code", [("is_deactivated", True, "ACCOUNT_DEACTIVATED"),
    ("account_status", "PENDING_VERIFICATION", "FORBIDDEN_ROLE"),
    ("account_status", "VERIFICATION_EXPIRED", "FORBIDDEN_ROLE")])
def test_ineligible_superadmin_denied_before_request_lookup(db_session, db_client, records, reviewer, monkeypatch, field, value, code):
    _, _, request, _, _ = records
    setattr(reviewer, field, value)
    db_session.commit()

    def forbidden(*args, **kwargs):
        pytest.fail("Deactivated reviewer reached data lookup")

    monkeypatch.setattr("app.modules.profile_change.repository.ProfileChangeRepository.get", forbidden)
    response = detail(db_client, request)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == code


def test_missing_detail_is_safe_404(db_client, records, reviewer):
    response = db_client.get("/api/v1/profile-change-requests/999999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CHANGE_REQUEST_NOT_FOUND"
