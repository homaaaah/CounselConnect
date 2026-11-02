from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import Mock

from app.modules.appointments.service import AppointmentsService


def schedule(*, mode="BOTH"):
    return SimpleNamespace(
        weekly_schedule_id=12,
        counselor_user_id=25,
        campus_id=1,
        day_of_week=4,
        start_time=time(8),
        end_time=time(9),
        slot_duration_minutes=60,
        delivery_mode=mode,
    )


def service_with(existing):
    service = object.__new__(AppointmentsService)
    service.repository = Mock()
    service.repository.active_weekly_schedules.return_value = [schedule()]
    # Materialization now prefetches the range once instead of per-slot reads.
    service.repository.availability_blocks_in_range.return_value = []
    service.repository.slots_in_range.return_value = [existing] if existing is not None else []
    return service


def existing_slot(**overrides):
    # Generated 08:00-09:00 Asia/Manila on 2026-09-17 is 00:00-01:00 UTC.
    return SimpleNamespace(
        counselor_user_id=25,
        campus_id=1,
        starts_at=datetime(2026, 9, 17, 0, 0),
        ends_at=datetime(2026, 9, 17, 1, 0),
        **overrides,
    )


def test_active_schedule_updates_matching_available_slot_mode():
    existing = existing_slot(
        status="AVAILABLE", delivery_mode="FACE_TO_FACE", weekly_schedule_id=None
    )
    service = service_with(existing)

    service.ensure_schedule_slots(date(2026, 9, 17), date(2026, 9, 17), 25)

    assert existing.delivery_mode == "BOTH"
    assert existing.weekly_schedule_id == 12
    service.repository.session.flush.assert_called_once_with()
    service.repository.session.add.assert_not_called()


def test_active_schedule_does_not_change_reserved_slot():
    existing = existing_slot(
        status="RESERVED", delivery_mode="FACE_TO_FACE", weekly_schedule_id=None
    )
    service = service_with(existing)

    service.ensure_schedule_slots(date(2026, 9, 17), date(2026, 9, 17), 25)

    assert existing.delivery_mode == "FACE_TO_FACE"
    assert existing.weekly_schedule_id is None
    service.repository.session.flush.assert_not_called()
    service.repository.session.add.assert_not_called()


def test_newly_extended_schedule_materializes_each_full_future_slot():
    service = object.__new__(AppointmentsService)
    service.repository = Mock()
    service.repository.active_weekly_schedules.return_value = [SimpleNamespace(
        weekly_schedule_id=15,
        counselor_user_id=25,
        campus_id=1,
        day_of_week=3,
        start_time=time(8),
        end_time=time(15),
        slot_duration_minutes=60,
        delivery_mode="BOTH",
    )]
    service.repository.availability_blocks_in_range.return_value = []
    service.repository.slots_in_range.return_value = []

    service.ensure_schedule_slots(date(2026, 9, 16), date(2026, 9, 16), 25)

    slots = [call.args[0] for call in service.repository.session.add.call_args_list]
    assert [(slot.starts_at.hour, slot.ends_at.hour) for slot in slots] == [
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7),
    ]
    assert all(slot.delivery_mode == "BOTH" and slot.weekly_schedule_id == 15 for slot in slots)
    service.repository.session.flush.assert_called_once_with()
