"""Login/status races serialize through the same target User lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.accounts.models import User
from app.modules.accounts.service import AccountsService
from app.modules.auth.models import UserSession
from app.modules.auth.service import AuthService
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from .test_correction_decision_concurrency import committed_correction  # noqa: F401


@pytest.mark.parametrize("scenario", ["login_first", "disable_first", "disable_twice"])
def test_status_and_session_issuance_have_no_live_session_escape(mysql_test_engine, committed_correction, monkeypatch, scenario):
    data = committed_correction
    held, competing, release = Event(), Event(), Event()
    issue, record = AuthService._issue_session, AuditService.record
    ids = []
    def pause_issue(self, user):
        result = issue(self, user)
        if self.repository.session.info.get("hold_login"):
            held.set()
            assert release.wait(10)
        return result
    def pause_status(self, actor, event_type, *args, **kwargs):
        result = record(self, actor, event_type, *args, **kwargs)
        if event_type == "account_deactivated" and self.repository.session.info.get("hold_status"):
            self.repository.session.flush()
            held.set()
            assert release.wait(10)
        return result
    monkeypatch.setattr(AuthService, "_issue_session", pause_issue)
    monkeypatch.setattr(AuditService, "record", pause_status)
    def observe(connection, _cursor, statement, params, _context, _many):
        if connection.info.get("manager_waiter") and "FROM users" in statement and "FOR UPDATE" in statement and data["student"] in params.values():
            competing.set()
    def act(first):
        with Session(mysql_test_engine, expire_on_commit=False, autoflush=False) as db:
            db.execute(text("SET SESSION innodb_lock_wait_timeout=5"))
            db.connection().info["manager_waiter"] = not first
            ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            login_action = (first and scenario == "login_first") or (not first and scenario == "disable_first")
            db.info["hold_login"] = first and login_action
            db.info["hold_status"] = first and not login_action
            try:
                if login_action:
                    student = db.get(User, data["student"])
                    AuthService(db).login(student.email, "password1")
                    db.commit()
                    return "LOGIN"
                actor = db.get(User, data["reviewers"][0 if first else 1])
                AccountsService(db).change_user_status(actor, data["student"], deactivated=True)
                return "DISABLED"
            except AppError as exc:
                db.rollback()
                return exc.code
            finally:
                db.connection().info["manager_waiter"] = False
    event.listen(mysql_test_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(act, True)
            try:
                assert held.wait(10)
                second = executor.submit(act, False)
                assert competing.wait(10)
            finally:
                release.set()
            results = first.result(timeout=15), second.result(timeout=15)
        assert len(set(ids)) == 2
        assert results == {"login_first": ("LOGIN", "DISABLED"), "disable_first": ("DISABLED", "ACCOUNT_DEACTIVATED"),
                           "disable_twice": ("DISABLED", "DISABLED")}[scenario]
        with Session(mysql_test_engine) as db:
            assert db.get(User, data["student"]).is_deactivated is True
            assert list(db.scalars(select(UserSession).where(UserSession.user_id == data["student"],
                UserSession.revoked_at.is_(None)))) == []
            audits = list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "account_deactivated",
                AuditEvent.target_id == data["student"])))
            assert len(audits) == 1
    finally:
        release.set()
        event.remove(mysql_test_engine, "before_cursor_execute", observe)
        with Session(mysql_test_engine) as db:
            db.execute(delete(AuditEvent).where(AuditEvent.event_type == "account_deactivated", AuditEvent.target_id == data["student"]))
            db.commit()
