"""Slot-list service preserves repository pagination and authorization."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppError
from app.modules.appointments.service import AppointmentsService


@pytest.mark.parametrize("count,total,page", [(20, 45, 1), (5, 45, 3), (0, 45, 4)])
def test_preserves_filtered_total(count, total, page):
    service = object.__new__(AppointmentsService)
    service.repository = Mock()
    slots = [SimpleNamespace(slot_id=i, counselor_user_id=1) for i in range(count)]
    service.repository.slots.return_value = (slots, total)
    service.slot_response = lambda slot: {"slot_id": slot.slot_id}
    actor = SimpleNamespace(role_code="STUDENT", account_status="ACTIVE")
    result = service.list_slots(actor, page=page)
    assert result == {"items": [{"slot_id": i} for i in range(count)],
                      "total": total, "page": page, "page_size": 20}


@pytest.mark.parametrize("role,status", [
    ("GUIDANCE_STAFF", "ACTIVE"), ("STUDENT", "PENDING_VERIFICATION"),
    ("STUDENT", "VERIFICATION_EXPIRED"),
])
def test_denies_before_query(role, status):
    service = object.__new__(AppointmentsService)
    service.repository = Mock()
    with pytest.raises(AppError):
        service.list_slots(SimpleNamespace(role_code=role, account_status=status))
    service.repository.slots.assert_not_called()
