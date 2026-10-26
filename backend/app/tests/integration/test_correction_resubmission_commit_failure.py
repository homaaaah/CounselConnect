"""Failed final commit releases rows and retries failed private-byte deletion."""

from datetime import datetime, timedelta, timezone

import pytest
from pymysql.err import OperationalError as MysqlOperationalError
from sqlalchemy.exc import OperationalError

from app.core.exceptions import AppError
from app.modules.cor_screening.service import CorScreeningService
from .test_correction_resubmission_transaction import counts, revise, stored_paths  # noqa: F401
from .test_correction_resubmission_preflight import returned_context  # noqa: F401


@pytest.mark.parametrize("delete_fails", [False, True])
def test_failed_final_commit_rolls_back_and_retries_only_its_orphan(
    db_session, returned_context, stored_paths, monkeypatch, caplog, delete_fails,
):
    _, user, enrolled, profile, previous, _, _ = returned_context
    before = counts(db_session)
    delete = CorScreeningService._delete_cor_bytes
    def fail_commit():
        raise OperationalError("PRIVATE SQL", {}, MysqlOperationalError(1213, "PRIVATE DRIVER"))
    def selective_delete(self, key):
        if delete_fails and len(stored_paths) == 2:
            return False
        return delete(self, key)
    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", fail_commit)
        patch.setattr(CorScreeningService, "_delete_cor_bytes", selective_delete)
        with pytest.raises(AppError) as caught:
            revise(db_session, returned_context)
    assert caught.value.code == "INTERNAL_ERROR" and "PRIVATE" not in caught.value.message
    assert counts(db_session) == before
    db_session.refresh(previous)
    db_session.refresh(profile)
    assert previous.status == "RETURNED" and profile.section == "A"
    assert enrolled.status == "PASSED" and user.account_status == "ACTIVE"
    assert len(stored_paths) == 2 and not stored_paths[0].exists()
    pending = stored_paths[1].with_suffix(".pending")
    if delete_fails:
        assert stored_paths[1].exists() and pending.exists()
        assert "cor_screening_upload_cleanup_retry_required" in caplog.text
        assert str(stored_paths[1]) not in caplog.text
        # Existing bounded abandoned-upload retry owns the marker; no new worker.
        CorScreeningService(db_session)._cleanup_abandoned_uploads(datetime.now(timezone.utc) + timedelta(days=8))
    assert not stored_paths[1].exists() and not pending.exists()
