"""A deactivated participant cannot keep signaling on an established call."""

from sqlalchemy.orm import Session

from app.modules.accounts.models import User
from .test_calls import call_data, committed_client, socket_engine, _appointment, _login, _ready  # noqa: F401


def test_live_call_rechecks_deactivation_before_signal(committed_client, call_data, mysql_test_engine, socket_engine):
    appointment_id = _appointment(mysql_test_engine, call_data)
    _login(committed_client, call_data["emails"]["student"])
    with _ready(appointment_id, committed_client) as socket:
        assert socket.receive_json()["type"] == "room-state"
        with Session(mysql_test_engine) as db:
            db.get(User, call_data["student_id"]).is_deactivated = True
            db.commit()
        socket.send_json({"type": "ready"})
        assert socket.receive_json() == {"type": "call-ended", "reason": "CALL_UNAVAILABLE"}
