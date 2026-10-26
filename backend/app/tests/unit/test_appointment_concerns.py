import pytest
from pydantic import ValidationError

from app.modules.appointments.schemas import AppointmentCreateRequest


def test_booking_concern_selection_preserves_priority_order():
    request = AppointmentCreateRequest(
        availability_slot_id=1,
        appointment_mode="ONLINE",
        concern_categories=["ACADEMIC_PROBLEM", "FAMILY_PROBLEM"],
    )
    assert request.concern_categories == ["ACADEMIC_PROBLEM", "FAMILY_PROBLEM"]
    assert request.concern_details is None


@pytest.mark.parametrize(
    "categories,details",
    [
        ([], None),
        (["FAMILY_PROBLEM", "FAMILY_PROBLEM"], None),
        (["ALL_OF_THE_ABOVE"], None),
        (["CUSTOM"], None),
        (["CUSTOM"], "  "),
        (["CUSTOM"], "x" * 501),
    ],
)
def test_booking_concern_validation_rejects_invalid_selection(categories, details):
    with pytest.raises(ValidationError):
        AppointmentCreateRequest(
            availability_slot_id=1,
            appointment_mode="ONLINE",
            concern_categories=categories,
            concern_details=details,
        )


def test_custom_concern_accepts_bounded_description_with_other_tags():
    request = AppointmentCreateRequest(
        availability_slot_id=1,
        appointment_mode="ONLINE",
        concern_categories=["CUSTOM", "RELATIONSHIP_PROBLEM"],
        concern_details="A short student-provided description.",
    )
    assert request.concern_categories[0] == "CUSTOM"
