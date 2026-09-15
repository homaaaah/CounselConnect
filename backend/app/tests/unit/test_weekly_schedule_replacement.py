"""Atomic recurring-schedule replacement without persistence dependencies."""

from datetime import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppError
from app.modules.appointments.schemas import WeeklyScheduleCreateRequest
from app.modules.appointments.service import AppointmentsService


def actor():
    return SimpleNamespace(user_id=9, role_code="COUNSELOR", account_status="ACTIVE")


def data(**overrides):
    values = dict(
        campus_id=4,
        day_of_week=1,
        start_time=time(8),
        end_time=time(10),
        slot_duration_minutes=30,
        delivery_mode="ONLINE",
    )
    values.update(overrides)
    return WeeklyScheduleCreateRequest(**values)


def schedule(schedule_id, **overrides):
    values = dict(weekly_schedule_id=schedule_id, is_active=True, **data().model_dump())
    values.update(overrides)
    return SimpleNamespace(**values)


def replacement_service(previous, replacement=None):
    service = object.__new__(AppointmentsService)
    service.repository = Mock()
    service.repository.lock_weekly_schedule.return_value = previous
    service.repository.overlapping_weekly_schedule.return_value = None
    service.repository.matching_weekly_schedule.return_value = None
    service.repository.create_weekly_schedule.return_value = replacement
    service.repository.session = Mock()
    service._participants = Mock()
    service._campus = Mock(return_value=SimpleNamespace(guidance_office_location="Office 101"))
    service.audit = Mock()
    return service


def test_replacement_excludes_previous_schedule_from_overlap_and_is_atomic():
    previous = schedule(7)
    replacement = schedule(8, end_time=time(11))
    service = replacement_service(previous, replacement)

    result = service.replace_weekly_schedule(actor(), 7, data(end_time=time(11)))

    assert result is replacement
    assert previous.is_active is False
    service.repository.overlapping_weekly_schedule.assert_called_once_with(
        9, 1, time(8), time(11), exclude_id=7
    )
    service.repository.create_weekly_schedule.assert_called_once_with(
        counselor_user_id=9, campus_id=4, day_of_week=1, start_time=time(8),
        end_time=time(11), slot_duration_minutes=30, delivery_mode="ONLINE",
    )
    service.repository.session.flush.assert_called_once()
    service.audit.record.assert_called_once_with(
        9, "weekly_schedule_replaced", "counselor_weekly_schedule", 7
    )


def test_replacement_conflict_leaves_previous_schedule_active():
    previous = schedule(7)
    service = replacement_service(previous)
    service.repository.overlapping_weekly_schedule.return_value = schedule(12)

    with pytest.raises(AppError, match="overlaps"):
        service.replace_weekly_schedule(actor(), 7, data(end_time=time(11)))

    assert previous.is_active is True
    service.repository.create_weekly_schedule.assert_not_called()
    service.repository.session.flush.assert_not_called()


def test_replacement_reactivates_identical_inactive_history_without_duplicate():
    previous = schedule(7)
    historical = schedule(4, is_active=False, end_time=time(11))
    service = replacement_service(previous)
    service.repository.matching_weekly_schedule.return_value = historical

    result = service.replace_weekly_schedule(actor(), 7, data(end_time=time(11)))

    assert result is historical
    assert historical.is_active is True
    assert previous.is_active is False
    service.repository.create_weekly_schedule.assert_not_called()


def test_replacing_with_unchanged_definition_is_a_noop():
    previous = schedule(7)
    service = replacement_service(previous)

    assert service.replace_weekly_schedule(actor(), 7, data()) is previous
    assert previous.is_active is True
    service.repository.overlapping_weekly_schedule.assert_not_called()
    service.repository.session.flush.assert_not_called()
