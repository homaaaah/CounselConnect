"""Session/CSRF-bound multipart revision API with safe owned 201 detail."""

from types import SimpleNamespace

import pytest

from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.profile_change.service import ProfileChangeService
from .test_correction_resubmission_preflight import returned_context  # noqa: F401
from .test_correction_approval_version import csrf
from .test_student_correction_reads import login


def parts(version="1", proposal='{"section":"B"}'):
    return [("submission_version", (None, version)), ("proposed_changes", (None, proposal)),
            ("file", ("fresh.pdf", b"%PDF-1.4 fresh API", "application/pdf"))]


def post(client, row, payload=None, headers=None):
    return client.post(f"/api/v1/profile-change-requests/{row.change_request_id}/resubmit",
        files=parts() if payload is None else payload, headers=csrf(client) if headers is None else headers)


@pytest.mark.parametrize("legacy", [False, True])
def test_owner_gets_safe_new_version_detail(db_session, db_client, returned_context, legacy):
    _, user, enrollment, profile, previous, _, _ = returned_context
    if legacy:
        previous.submission_version = None
        previous.status = "REJECTED"
        db_session.commit()
    login(db_client, user.email)
    result = post(db_client, previous, parts("null" if legacy else "1"))
    assert result.status_code == 201
    assert result.headers["cache-control"] == "no-store"
    body = result.json()
    row = body["change_request"]
    assert row["change_request_id"] != previous.change_request_id
    assert row["previous_change_request_id"] == previous.change_request_id
    assert row["submission_version"] == (1 if legacy else 2)
    assert row["status"] == "PENDING" and body["changed_fields"] == ["section"]
    assert body["current_section"] == "A" and row["requested_section"] == "B"
    for private in ("storage_key", "sha256", "verification_token", "reviewed_by_user_id", "extracted_values_json"):
        assert private not in result.text
    assert profile.section == "A" and user.account_status == "ACTIVE" and enrollment.status == "PASSED"
    own = db_client.get(f"/api/v1/profile-change-requests/{row['change_request_id']}")
    assert own.json() == body
    replay = post(db_client, previous, parts("null" if legacy else "1"))
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "CHANGE_REQUEST_VERSION_CONFLICT"
    service = ProfileChangeService(db_session)
    service.return_request(service.accounts.find_user_by_email("edit-super@example.edu"),
        row["change_request_id"], "Recheck section.", submission_version=row["submission_version"])


@pytest.mark.parametrize("case", ["extra", "duplicate_version", "duplicate_file", "duplicate_proposal", "missing_file",
    "missing_version", "missing_proposal", "bad_version", "bool_version", "zero_version", "wrong_version",
    "invalid_json", "protected", "no_changes", "bad_pdf"])
def test_strict_multipart_denials_leave_predecessor_unchanged(db_client, returned_context, case):
    _, user, _, profile, previous, _, _ = returned_context
    login(db_client, user.email)
    payload = parts()
    if case == "extra":
        payload.append(("student_user_id", (None, "PRIVATE")))
    elif case.startswith("duplicate_"):
        payload.append(payload[{"duplicate_version": 0, "duplicate_proposal": 1, "duplicate_file": 2}[case]])
    elif case.startswith("missing_"):
        payload = [part for part in payload if part[0] != {"missing_version": "submission_version",
            "missing_proposal": "proposed_changes", "missing_file": "file"}[case]]
    elif case in {"bad_version", "bool_version", "zero_version", "wrong_version"}:
        payload = parts({"bad_version": "1.0", "bool_version": "true", "zero_version": "0", "wrong_version": "2"}[case])
    elif case in {"invalid_json", "protected", "no_changes"}:
        payload = parts(proposal={"invalid_json": "{PRIVATE", "protected": '{"student_number":"PRIVATE"}', "no_changes": "{}"}[case])
    else:
        payload[-1] = ("file", ("cor.pdf", b"PRIVATE invalid", "application/pdf"))
    result = post(db_client, previous, payload)
    assert result.status_code == (409 if case == "wrong_version" else 422)
    assert "PRIVATE" not in result.text
    assert previous.status == "RETURNED" and profile.section == "A"


@pytest.mark.parametrize("csrf_header", [{}, {"X-CSRF-Token": "wrong"}])
def test_missing_or_wrong_csrf_is_denied(db_client, returned_context, csrf_header):
    login(db_client, returned_context[1].email)
    assert post(db_client, returned_context[4], headers=csrf_header).status_code == 403


def test_token_alone_cannot_authorize_revision(db_client, returned_context):
    result = post(db_client, returned_context[4], headers={"X-COR-Token": "cor-token"})
    assert result.status_code == 401


@pytest.mark.parametrize("role", ["COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN", "STUDENT"])
def test_staff_and_other_student_cannot_resubmit(db_session, db_client, returned_context, role):
    other = User(email="other-revision@example.edu", password_hash=hash_password("password1"),
        role_code=role, account_status="ACTIVE", first_name="Other", last_name="User")
    db_session.add(other)
    db_session.commit()
    login(db_client, other.email)
    result = post(db_client, returned_context[4])
    assert result.status_code == (404 if role == "STUDENT" else 403)
    assert result.json()["error"]["code"] == ("CHANGE_REQUEST_NOT_FOUND" if role == "STUDENT" else "FORBIDDEN_ROLE")


def test_oversize_read_is_bounded_before_service(db_client, returned_context, monkeypatch):
    import app.modules.profile_change.router as module
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(cor_max_mb=1))
    login(db_client, returned_context[1].email)
    payload = parts()
    payload[-1] = ("file", ("cor.pdf", b"%PDF" + b"x" * (1024 * 1024), "application/pdf"))
    result = post(db_client, returned_context[4], payload)
    assert result.status_code == 422 and result.json()["error"]["code"] == "COR_TOO_LARGE"


@pytest.mark.parametrize("deactivated", [False, True])
def test_current_eligibility_is_enforced_with_existing_session(db_session, db_client, returned_context, deactivated):
    _, user, _, profile, previous, _, _ = returned_context
    login(db_client, user.email)
    headers = csrf(db_client)
    if deactivated:
        user.is_deactivated = True
    else:
        user.account_status = "VERIFICATION_EXPIRED"
    db_session.commit()
    result = post(db_client, previous, headers=headers)
    assert result.status_code == (403 if deactivated else 409)
    assert previous.status == "RETURNED" and profile.section == "A"


def test_missing_request_matches_foreign_not_found(db_client, returned_context):
    login(db_client, returned_context[1].email)
    result = post(db_client, SimpleNamespace(change_request_id=999999))
    assert result.status_code == 404
    assert result.json()["error"]["code"] == "CHANGE_REQUEST_NOT_FOUND"
