"""API contract tests: registration + public content endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_register_student_creates_pending_account(db_client: TestClient, academic_references):
    import uuid

    suffix = uuid.uuid4().hex[:8]
    payload = {
        "email": f"student-{suffix}@example.edu",
        "password": "secure-password-1",
        "first_name": "Juan",
        "middle_name": "Reyes",
        "last_name": "Dela Cruz",
        "student_number": f"2026-{suffix}",
        "campus_id": academic_references[0],
        "program_id": academic_references[1],
        "year_level": 1,
        "section": "A",
    }
    response = db_client.post("/api/v1/accounts/register/student", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["account_status"] == "PENDING_VERIFICATION"
    assert body["user"]["role_code"] == "STUDENT"
    assert "COR" in body["next_step"]


def test_register_student_validation_error(client: TestClient):
    response = client.post(
        "/api/v1/accounts/register/student",
        json={"email": "not-an-email", "password": "x"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_unknown_identifier_is_401_envelope(db_client: TestClient):
    """ADR-019: real login exists; unknown credentials get the same 401
    error either way (never reveal which part failed)."""
    response = db_client.post(
        "/api/v1/auth/login",
        json={"identifier": "student1@example.edu", "password": "irrelevant"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_public_content_endpoints_respond(db_client: TestClient):
    for path in (
        "/api/v1/content/cms-blocks",
        "/api/v1/content/faqs",
        "/api/v1/content/announcements",
        "/api/v1/content/emergency-contacts",
    ):
        response = db_client.get(path)
        assert response.status_code == 200
        assert "items" in response.json()
