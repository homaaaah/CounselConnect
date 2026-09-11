"""Calendar aggregation without a database; persistence is covered in integration tests."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppError
from app.modules.appointments import service as module


def calendar_service(monkeypatch):
    monkeypatch.setattr(module, "utcnow", lambda: datetime(2026, 9, 11, 5, 30))
    service = object.__new__(module.AppointmentsService)
    service.repository = Mock()
    service.ensure_schedule_slots = Mock()
    service.repository.active_counselor_ids.return_value = [1, 2]
    service.repository.blocked_dates.return_value = set()
    service.repository.calendar_slots.return_value = []
    return service


def test_calendar_uses_real_unique_times_and_owner_blocks(monkeypatch):
    service = calendar_service(monkeypatch)
    today = date(2026, 9, 11)
    student = SimpleNamespace(role_code="STUDENT", account_status="ACTIVE", user_id=3)
    assert service.calendar(student, today, today)["days"][0]["available_times"] == []
    service.repository.calendar_slots.return_value = [
        SimpleNamespace(counselor_user_id=owner, starts_at=datetime(2026, 9, 11, hour, minute))
        for owner, hour, minute in [(1, 6, 0), (1, 6, 30), (2, 6, 30), (2, 7, 0)]
    ]
    assert service.calendar(student, today, today)["days"][0]["available_times"] == ["14:00", "14:30", "15:00"]
    service.repository.blocked_dates.side_effect = lambda ids, *_: {today} if ids == [1] else set()
    day = service.calendar(student, today, today)["days"][0]
    assert day["available_times"] == ["14:30", "15:00"]
    assert day["is_blocked"] is False
    service.repository.calendar_slots.assert_called_with(
        [1, 2], datetime(2026, 9, 11, 5, 30), datetime(2026, 9, 10, 16), datetime(2026, 9, 11, 16)
    )


def test_calendar_counselor_scope_and_past_dates(monkeypatch):
    service = calendar_service(monkeypatch)
    actor = SimpleNamespace(role_code="COUNSELOR", account_status="ACTIVE", user_id=2)
    days = service.calendar(actor, date(2026, 9, 10), date(2026, 9, 11))["days"]
    assert days[0]["is_past"] is True
    assert days[0]["available_times"] == []
    service.ensure_schedule_slots.assert_called_once_with(date(2026, 9, 11), date(2026, 9, 11), 2)
    assert service.repository.calendar_slots.call_args.args[0] == [2]


@pytest.mark.parametrize("role,status", [("GUIDANCE_STAFF", "ACTIVE"), ("STUDENT", "PENDING_VERIFICATION")])
def test_calendar_rejects_unauthorized_before_loading(monkeypatch, role, status):
    service = calendar_service(monkeypatch)
    with pytest.raises(AppError):
        service.calendar(SimpleNamespace(role_code=role, account_status=status, user_id=3), date(2026, 9, 11), date(2026, 9, 11))
    service.repository.calendar_slots.assert_not_called()
