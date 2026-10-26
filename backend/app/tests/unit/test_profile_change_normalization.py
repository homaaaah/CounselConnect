"""Shared normalization vectors and safe registration field validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.exceptions import AppError
from app.modules.cor_screening.schemas import ConfirmScreeningRequest, RequestEditRequest
from app.modules.profile_change.normalization import normalize_profile_fields, normalize_text
from app.modules.profile_change.service import ProfileChangeService

CASES = json.loads((Path(__file__).resolve().parents[4] / "contracts" / "registration-normalization-cases.json").read_text(encoding="utf-8"))
BASE = dict(first_name="Ana", middle_name=None, last_name="Cruz", year_level=1, section="A")


@pytest.mark.parametrize("case", CASES)
def test_shared_normalization_vectors(case):
    field = case["field"]
    extracted = normalize_profile_fields(**{**BASE, field: case["extracted"]})
    proposed = normalize_profile_fields(**{**BASE, field: case["proposed"]})
    assert proposed[field] == case["canonical"]
    changed = (extracted[field] != proposed[field] if field == "year_level" else
               normalize_text(extracted[field]).casefold() != normalize_text(proposed[field]).casefold())
    assert changed is case["changed"]
    assert ProfileChangeService._validate_requested(**{**BASE, field: case["proposed"]})[f"requested_{field}"] == case["canonical"]


@pytest.mark.parametrize("schema", [ConfirmScreeningRequest, RequestEditRequest])
def test_dto_normalizes_before_length_validation(schema):
    values = {**BASE, "student_number": "20231234-A", "campus_id": 1, "program_id": 1,
              "first_name": " " * 120 + "Ana\t Maria" + " " * 120, "middle_name": " \t "}
    dto = schema(**values)
    assert dto.first_name == "Ana Maria"
    assert dto.middle_name is None


@pytest.mark.parametrize("year", [True, False, 1.5, "1", 0, 11])
def test_request_rejects_non_integer_or_out_of_range_year(year):
    with pytest.raises(ValidationError):
        RequestEditRequest(**{**BASE, "student_number": "20231234-A", "campus_id": 1,
                              "program_id": 1, "year_level": year})


@pytest.mark.parametrize("changes", [
    {"first_name": " \t "}, {"last_name": None}, {"section": "\u00a0"},
    {"first_name": "x" * 101}, {"middle_name": "x" * 101}, {"section": "x" * 51},
    {"year_level": True}, {"year_level": 1.5},
])
def test_service_validates_canonical_values_even_without_dto(changes):
    with pytest.raises(AppError) as error:
        normalize_profile_fields(**{**BASE, **changes})
    assert error.value.code == "INVALID_PROFILE_EDIT"
