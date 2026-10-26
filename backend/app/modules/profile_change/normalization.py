"""Canonical values for the five supported registration correction fields."""

import json

from app.core.exceptions import AppError


def normalize_text(value: str | None) -> str:
    """Collapse Unicode whitespace without changing case or punctuation."""
    return " ".join((value or "").split())


def normalize_profile_fields(
    first_name: str | None, middle_name: str | None, last_name: str | None,
    year_level: int | None, section: str | None,
) -> dict[str, object]:
    values = {}
    for field, value, limit in (
        ("first_name", first_name, 100), ("middle_name", middle_name, 100),
        ("last_name", last_name, 100), ("section", section, 50),
    ):
        if value is not None and not isinstance(value, str):
            raise AppError(code="INVALID_PROFILE_EDIT", message="Enter valid registration information.", status_code=422)
        normalized = normalize_text(value)
        if len(normalized) > limit or (field != "middle_name" and not normalized):
            raise AppError(code="INVALID_PROFILE_EDIT", message="Name or section is blank or too long.", status_code=422)
        values[field] = normalized or None
    # bool is an int subclass; never coerce booleans or truncate fractions.
    if type(year_level) is not int or not 1 <= year_level <= 10:
        raise AppError(code="INVALID_PROFILE_EDIT", message="Enter a valid integer year level.", status_code=422)
    values["year_level"] = year_level
    return values


def normalize_resubmission_proposal(proposed_changes: object, *, baseline: dict) -> dict[str, object]:
    """Merge an editable-only revision into the actual current registered baseline."""
    fields = ("first_name", "middle_name", "last_name", "year_level", "section")
    if not isinstance(proposed_changes, dict):
        raise AppError(code="INVALID_PROFILE_EDIT", message="Enter a registration correction object.", status_code=422)
    if any(field not in fields for field in proposed_changes):
        raise AppError(code="FIELD_NOT_EDITABLE", message="Only supported registration fields may be corrected.", status_code=422)
    current = normalize_profile_fields(**{field: baseline.get(field) for field in fields})
    proposed = normalize_profile_fields(**{**current, **proposed_changes})
    if all(current[field] == proposed[field] if field == "year_level" else
           normalize_text(current[field]).casefold() == normalize_text(proposed[field]).casefold()
           for field in fields):
        raise AppError(code="NO_CORRECTION_CHANGES", message="Change at least one registration field.", status_code=422)
    return proposed


def parse_resubmission_proposal(raw: str, *, baseline: dict) -> dict[str, object]:
    """Parse multipart proposed_changes without ambiguous keys or non-JSON numbers."""
    def object_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("Invalid JSON number")

    try:
        if not isinstance(raw, str):
            raise ValueError("Expected JSON text")
        parsed = json.loads(raw, object_pairs_hook=object_fields, parse_constant=invalid_constant)
    except (ValueError, RecursionError):
        raise AppError(code="INVALID_PROFILE_EDIT", message="Enter a valid registration correction object.", status_code=422) from None
    return normalize_resubmission_proposal(parsed, baseline=baseline)
