"""Opt-in Counselor account forms against real browser/API/disposable MySQL."""

import os

import pytest

from .test_correction_decision_concurrency import committed_correction  # noqa: F401
from .test_management_frontend import run_management_workflows


@pytest.mark.skipif(os.environ.get("COUNSELCONNECT_BROWSER_REHEARSAL") != "1", reason="Opt-in Playwright/Chrome test")
@pytest.mark.parametrize("committed_correction", ["REGISTRATION"], indirect=True)
@pytest.mark.parametrize("viewport", ["desktop", "mobile"])
def test_counselor_account_browser(mysql_test_engine, committed_correction, tmp_path, viewport):
    run_management_workflows(mysql_test_engine, committed_correction, script="browser-management.cjs", extra_env={
        "COUNSELCONNECT_TEST_COUNSELORS": "1", "COUNSELCONNECT_TEST_VIEWPORT": viewport,
        "COUNSELCONNECT_TEST_ARTIFACTS": str(tmp_path),
    })
