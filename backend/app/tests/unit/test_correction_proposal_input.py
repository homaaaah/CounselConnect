"""Strict multipart revision inputs and current-baseline normalization."""

from copy import deepcopy
import json

import pytest

from app.core.exceptions import AppError
from app.modules.profile_change.normalization import parse_resubmission_proposal
from .test_profile_change_normalization import BASE, CASES


@pytest.mark.parametrize("case", CASES)
def test_shared_vectors_apply_to_partial_revision(case):
    baseline = {**BASE, case["field"]: case["extracted"]}
    raw = json.dumps({case["field"]: case["proposed"]})
    if not case["changed"]:
        with pytest.raises(AppError) as caught:
            parse_resubmission_proposal(raw, baseline=baseline)
        assert caught.value.code == "NO_CORRECTION_CHANGES"
    else:
        assert parse_resubmission_proposal(raw, baseline=baseline)[case["field"]] == case["canonical"]


def test_partial_revision_uses_current_baseline_and_does_not_mutate_it():
    baseline = {**BASE, "middle_name": "Current", "student_number": "20231234-A"}
    original = deepcopy(baseline)
    result = parse_resubmission_proposal('{"section":"  B\\t 2  "}', baseline=baseline)
    assert result == {**BASE, "middle_name": "Current", "section": "B 2"}
    assert baseline == original


@pytest.mark.parametrize("middle", [None, "", " \t\u00a0 "])
def test_middle_name_can_be_explicitly_removed(middle):
    result = parse_resubmission_proposal(json.dumps({"middle_name": middle}), baseline={**BASE, "middle_name": "Reyes"})
    assert result["middle_name"] is None


@pytest.mark.parametrize("raw", ["{}", '{"first_name":" ANA "}', '{"middle_name":null}', '{"year_level":1}'])
def test_empty_or_case_whitespace_equivalent_revision_is_rejected(raw):
    with pytest.raises(AppError) as caught:
        parse_resubmission_proposal(raw, baseline=BASE)
    assert caught.value.code == "NO_CORRECTION_CHANGES"


@pytest.mark.parametrize("field", ["student_number", "campus_id", "program_id", "academic_period", "user_id",
    "status", "submission_version", "root_change_request_id", "evidence_file_id", "purpose", "__proto__"])
def test_protected_and_unknown_fields_are_rejected(field):
    with pytest.raises(AppError) as caught:
        parse_resubmission_proposal(json.dumps({"section": "B", field: "PRIVATE"}), baseline=BASE)
    assert caught.value.code == "FIELD_NOT_EDITABLE"
    assert "PRIVATE" not in caught.value.message


@pytest.mark.parametrize("proposal", [
    {"first_name": None}, {"last_name": None}, {"section": None}, {"year_level": None},
    {"first_name": " "}, {"last_name": []}, {"section": {}}, {"middle_name": 1},
    {"year_level": True}, {"year_level": "2"}, {"year_level": 2.0}, {"year_level": 0}, {"year_level": 11},
    {"first_name": "x" * 101}, {"last_name": "x" * 101}, {"middle_name": "x" * 101}, {"section": "x" * 51},
])
def test_invalid_values_are_not_coerced(proposal):
    with pytest.raises(AppError) as caught:
        parse_resubmission_proposal(json.dumps(proposal), baseline=BASE)
    assert caught.value.code == "INVALID_PROFILE_EDIT"


@pytest.mark.parametrize("raw", ["null", "[]", '"section"', "1", "true", "{", '{"section":"B"} trailing',
    '{"section":"B","section":"C"}', '{"year_level":NaN}', '{"year_level":Infinity}', None, {}])
def test_malformed_nonobject_or_ambiguous_json_is_rejected(raw):
    with pytest.raises(AppError) as caught:
        parse_resubmission_proposal(raw, baseline=BASE)
    assert caught.value.code == "INVALID_PROFILE_EDIT"
