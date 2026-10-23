"""Appointment call authorization, signaling isolation, and cleanup (ADR-034)."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.config import get_settings
from app.core.security import hash_password
from app.database import get_session
from app.modules.accounts.models import Campus, Department, Program, StudentProfile, User
from app.modules.appointments.models import Appointment, AvailabilitySlot
from app.modules.audit.models import AuditEvent
from app.modules.calls import realtime as call_realtime

ORIGIN = "http://localhost:5173"
PASSWORD = "synthetic-test-pass"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0)


def _user(session, suffix, role, *, status="ACTIVE"):
    user = User(
        email=f"call-{role.lower()}-{suffix}-{uuid4().hex[:8]}@example.edu",
        password_hash=hash_password(PASSWORD),
        role_code=role,
        account_status=status,
        first_name=role.title(),
        last_name="Call",
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture()
def call_data(mysql_test_engine):
    """Committed reference data so WS connections (separate sessions) can see it."""
    suffix = uuid4().hex[:8]
    with Session(mysql_test_engine, expire_on_commit=False) as session:
        campus = Campus(campus_name=f"Call Campus {suffix}", guidance_office_location="Room 101")
        department = Department(department_name=f"Call Department {suffix}")
        session.add_all([campus, department])
        session.flush()
        program = Program(
            department_id=department.department_id,
            program_code=f"C{suffix[:6].upper()}",
            program_name=f"Call Program {suffix}",
        )
        session.add(program)
        session.flush()

        student = _user(session, suffix, "STUDENT")
        counselor = _user(session, suffix, "COUNSELOR")
        other_student = _user(session, suffix, "STUDENT")
        other_counselor = _user(session, suffix, "COUNSELOR")
        staff = _user(session, suffix, "GUIDANCE_STAFF")
        pending = _user(session, suffix, "STUDENT", status="PENDING_VERIFICATION")
        session.add(
            StudentProfile(
                user_id=student.user_id,
                student_number=f"CALL-{suffix}-1",
                campus_id=campus.campus_id,
                program_id=program.program_id,
                year_level=1,
                section="A",
            )
        )
        session.add(
            StudentProfile(
                user_id=other_student.user_id,
                student_number=f"CALL-{suffix}-2",
                campus_id=campus.campus_id,
                program_id=program.program_id,
                year_level=1,
                section="A",
            )
        )
        session.commit()
        return {
            "campus_id": campus.campus_id,
            "student_id": student.user_id,
            "counselor_id": counselor.user_id,
            "other_student_id": other_student.user_id,
            "other_counselor_id": other_counselor.user_id,
            "staff_id": staff.user_id,
            "pending_id": pending.user_id,
            "emails": {
                "student": student.email,
                "counselor": counselor.email,
                "other_student": other_student.email,
                "other_counselor": other_counselor.email,
                "staff": staff.email,
                "pending": pending.email,
            },
        }


def _appointment(
    engine,
    data,
    *,
    status="CONFIRMED",
    mode="ONLINE",
    start_minutes=-5,
    end_minutes=55,
):
    with Session(engine, expire_on_commit=False) as session:
        now = _now()
        slot = AvailabilitySlot(
            counselor_user_id=data["counselor_id"],
            campus_id=data["campus_id"],
            delivery_mode="BOTH",
            starts_at=now + timedelta(minutes=start_minutes),
            ends_at=now + timedelta(minutes=end_minutes),
            status="RESERVED",
        )
        session.add(slot)
        session.flush()
        appointment = Appointment(
            student_user_id=data["student_id"],
            counselor_user_id=data["counselor_id"],
            availability_slot_id=slot.slot_id,
            appointment_mode=mode,
            meeting_location="Room 101" if mode == "FACE_TO_FACE" else None,
            status=status,
        )
        session.add(appointment)
        session.commit()
        return appointment.appointment_id


def _login(client: TestClient, email: str):
    response = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response


@pytest.fixture()
def committed_client(app, mysql_test_engine):
    """Client whose requests commit, so socket authentication can see sessions."""

    def override():
        session = Session(mysql_test_engine, expire_on_commit=False)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_session] = override
    return TestClient(app)


@pytest.fixture()
def socket_engine(mysql_test_engine, monkeypatch):
    monkeypatch.setattr(call_realtime, "get_engine", lambda: mysql_test_engine)
    return mysql_test_engine


def test_call_config_is_windowed_and_participant_only(
    committed_client, app, call_data, mysql_test_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])

    response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["can_call"] is True
    assert body["role"] == "STUDENT"
    assert body["peer_role"] == "COUNSELOR"
    assert body["ice_servers"][0]["urls"] == ["stun:stun.l.google.com:19302"]
    assert response.headers["cache-control"] == "no-store"

    counselor_client = TestClient(app)
    _login(counselor_client, call_data["emails"]["counselor"])
    response = counselor_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == 200
    assert response.json()["role"] == "COUNSELOR"
    assert response.json()["peer_role"] == "STUDENT"


def test_call_config_returns_configured_turn_servers(
    committed_client, call_data, mysql_test_engine, monkeypatch
):
    monkeypatch.setenv(
        "COUNSELCONNECT_CALL_ICE_SERVERS",
        json.dumps([
            {
                "urls": ["turn:turn.example.test:3478"],
                "username": "synthetic-turn-user",
                "credential": "synthetic-turn-credential",
            }
        ]),
    )
    get_settings.cache_clear()
    try:
        appointment_id = _appointment(mysql_test_engine, call_data)
        _login(committed_client, call_data["emails"]["student"])
        response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
        assert response.status_code == 200
        assert response.json()["ice_servers"] == [
            {
                "urls": ["turn:turn.example.test:3478"],
                "username": "synthetic-turn-user",
                "credential": "synthetic-turn-credential",
            }
        ]
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "start_minutes,end_minutes",
    [(20, 80), (-80, -40)],
)
def test_call_config_outside_window_has_no_ice_servers(
    committed_client, call_data, mysql_test_engine, start_minutes, end_minutes
):
    appointment_id = _appointment(
        mysql_test_engine, call_data, start_minutes=start_minutes, end_minutes=end_minutes
    )
    _login(committed_client, call_data["emails"]["student"])
    response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == 200
    assert response.json()["can_call"] is False
    assert response.json()["ice_servers"] == []


def test_call_config_rejects_face_to_face(committed_client, call_data, mysql_test_engine):
    appointment_id = _appointment(mysql_test_engine, call_data, mode="FACE_TO_FACE")
    _login(committed_client, call_data["emails"]["student"])
    response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == 200
    assert response.json()["can_call"] is False


@pytest.mark.parametrize(
    "status",
    ["PENDING", "REJECTED", "CANCELLED", "COMPLETED", "NO_SHOW"],
)
def test_call_config_rejects_non_confirmed_status(
    committed_client, call_data, mysql_test_engine, status
):
    appointment_id = _appointment(mysql_test_engine, call_data, status=status)
    _login(committed_client, call_data["emails"]["student"])
    response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == 200
    assert response.json()["can_call"] is False
    assert response.json()["ice_servers"] == []


@pytest.mark.parametrize(
    "email_key,expected",
    [
        ("other_student", 404),
        ("other_counselor", 404),
        ("staff", 403),
        ("pending", 403),
    ],
)
def test_call_config_denies_non_participants(
    committed_client, call_data, mysql_test_engine, email_key, expected
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"][email_key])
    response = committed_client.get(f"/api/v1/appointments/{appointment_id}/call")
    assert response.status_code == expected


def _ready(appointment_id, client: TestClient):
    return client.websocket_connect(
        f"/api/v1/appointments/{appointment_id}/call/ws", headers={"origin": ORIGIN}
    )


def test_socket_relays_signals_only_between_participants(
    committed_client, app, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    counselor_client = TestClient(app)

    _login(committed_client, call_data["emails"]["student"])
    _login(counselor_client, call_data["emails"]["counselor"])

    with _ready(appointment_id, committed_client) as student:
        assert student.receive_json()["type"] == "room-state"
        student.send_json({"type": "ready"})
        with _ready(appointment_id, counselor_client) as counselor:
            assert counselor.receive_json()["type"] == "room-state"
            counselor.send_json({"type": "ready"})
            joined = counselor.receive_json()
            assert joined["type"] == "room-state"
            assert joined["initiator"] is True
            assert student.receive_json()["type"] == "peer-joined"

            counselor.send_json({"type": "offer", "sdp": "v=0\r\noffer"})
            offer = student.receive_json()
            assert offer == {"type": "offer", "sdp": "v=0\r\noffer"}

            student.send_json({"type": "answer", "sdp": "v=0\r\nanswer"})
            answer = counselor.receive_json()
            assert answer == {"type": "answer", "sdp": "v=0\r\nanswer"}

            student.send_json(
                {"type": "ice-candidate", "candidate": {"candidate": "candidate:1"}}
            )
            candidate = counselor.receive_json()
            assert candidate["type"] == "ice-candidate"
            assert candidate["candidate"] == {"candidate": "candidate:1"}


def test_socket_rejects_unauthorized_origin_and_non_participants(
    committed_client, app, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["other_student"])
    with pytest.raises(WebSocketDisconnect):
        with committed_client.websocket_connect(
            f"/api/v1/appointments/{appointment_id}/call/ws",
            headers={"origin": "http://evil.example"},
        ):
            pass
    with pytest.raises(WebSocketDisconnect):
        with committed_client.websocket_connect(
            f"/api/v1/appointments/{appointment_id}/call/ws",
            headers={"origin": ORIGIN},
        ):
            pass


def test_socket_rejects_invalid_and_oversized_messages(
    committed_client, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        socket.send_json({"type": "not-a-signal"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()

    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        socket.send_text("x" * 70_000)
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_socket_replaces_a_duplicate_connection(
    committed_client, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    with _ready(appointment_id, committed_client) as first:
        assert first.receive_json()["type"] == "room-state"
        with _ready(appointment_id, committed_client) as second:
            assert second.receive_json() == {
                "type": "room-state",
                "peer_present": False,
                "initiator": False,
                "peer_role": None,
            }
            assert first.receive_json() == {"type": "call-ended", "reason": "REPLACED"}
            with pytest.raises(WebSocketDisconnect):
                first.receive_json()


def test_duplicate_connection_ends_the_paired_call(
    committed_client, app, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    counselor_client = TestClient(app)
    _login(committed_client, call_data["emails"]["student"])
    _login(counselor_client, call_data["emails"]["counselor"])

    with _ready(appointment_id, committed_client) as student:
        assert student.receive_json()["type"] == "room-state"
        student.send_json({"type": "ready"})
        with _ready(appointment_id, counselor_client) as counselor:
            assert counselor.receive_json()["type"] == "room-state"
            counselor.send_json({"type": "ready"})
            assert counselor.receive_json()["initiator"] is True
            assert student.receive_json()["type"] == "peer-joined"

            with _ready(appointment_id, committed_client) as second_student:
                assert second_student.receive_json()["peer_present"] is False
                assert student.receive_json() == {"type": "call-ended", "reason": "REPLACED"}
                assert counselor.receive_json() == {"type": "call-ended", "reason": "REPLACED"}


def test_socket_notifies_the_peer_when_a_participant_disconnects(
    committed_client, app, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    counselor_client = TestClient(app)
    _login(committed_client, call_data["emails"]["student"])
    _login(counselor_client, call_data["emails"]["counselor"])

    with _ready(appointment_id, counselor_client) as counselor:
        assert counselor.receive_json()["type"] == "room-state"
        counselor.send_json({"type": "ready"})
        with _ready(appointment_id, committed_client) as student:
            assert student.receive_json()["type"] == "room-state"
            student.send_json({"type": "ready"})
            assert student.receive_json()["initiator"] is True
            assert counselor.receive_json()["type"] == "peer-joined"

        assert counselor.receive_json() == {"type": "peer-left"}


def test_busy_client_is_revalidated_by_wall_clock(
    committed_client, call_data, mysql_test_engine, socket_engine, monkeypatch
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    monkeypatch.setattr(call_realtime, "SOCKET_REVALIDATE_SECONDS", 0.2)
    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        socket.send_json({"type": "ready"})
        with Session(mysql_test_engine) as session:
            appointment = session.get(Appointment, appointment_id)
            appointment.status = "CANCELLED"
            session.commit()
        for _ in range(8):
            try:
                socket.send_json({"type": "ready"})
            except Exception:
                break
            time.sleep(0.05)
        assert socket.receive_json() == {
            "type": "call-ended",
            "reason": "CALL_UNAVAILABLE",
        }


def test_socket_closes_when_the_appointment_is_no_longer_callable(
    committed_client, call_data, mysql_test_engine, socket_engine, monkeypatch
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    monkeypatch.setattr(call_realtime, "SOCKET_REVALIDATE_SECONDS", 0.1)
    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        socket.send_json({"type": "ready"})
        with Session(mysql_test_engine) as session:
            appointment = session.get(Appointment, appointment_id)
            appointment.status = "CANCELLED"
            session.commit()
        ended = socket.receive_json()
        assert ended["type"] == "call-ended"
        assert ended["reason"] == "CALL_UNAVAILABLE"


def test_signaling_creates_no_audit_events_or_call_rows(
    committed_client, call_data, mysql_test_engine, socket_engine
):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    with Session(mysql_test_engine) as session:
        before = session.scalar(select(func.count()).select_from(AuditEvent))
    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        socket.send_json({"type": "ready"})
        socket.send_json({"type": "hangup"})
    with Session(mysql_test_engine) as session:
        after = session.scalar(select(func.count()).select_from(AuditEvent))
    assert before == after
