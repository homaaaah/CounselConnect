"""Independent-connection races for Counselor identity writes and login."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.modules.accounts.models import User
from app.modules.accounts.schemas import CounselorAccountCreateRequest, CounselorAccountUpdateRequest
from app.modules.accounts.service import AccountsService
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditService
from app.modules.auth.models import UserSession
from app.modules.auth.service import AuthService


@pytest.fixture
def committed_counselor(mysql_test_engine):
    tag = uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as db:
        rows = [User(email=f"counselor-race-{tag}-{i}@example.edu", password_hash=hash_password("race-password"),
                     role_code="SUPERADMIN" if i < 2 else "COUNSELOR", account_status="ACTIVE",
                     first_name="Race", last_name=str(i)) for i in range(3)]
        db.add_all(rows); db.commit()
        target = rows[2]
        stamp = target.updated_at
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
        data = {"admins": [row.user_id for row in rows[:2]], "target": target.user_id,
                "old_email": target.email, "new_email": f"changed-{tag}@example.edu",
                "create_email": f"created-{tag}@example.edu", "stamp": stamp}
    try:
        yield data
    finally:
        with Session(mysql_test_engine) as db:
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(data["admins"])))
            db.execute(delete(User).where(User.user_id.in_([*data["admins"], data["target"]]) | (User.email == data["create_email"])))
            db.commit()


@pytest.mark.parametrize("scenario", ["edit_first", "login_first", "two_edits", "duplicate_create"])
def test_counselor_writes_serialize(mysql_test_engine, committed_counselor, monkeypatch, scenario):
    data = committed_counselor
    held, waiting, release = Event(), Event(), Event()
    connection_ids = []
    audit, issue = AuditService.record, AuthService._issue_session

    def pause_audit(self, *args, **kwargs):
        result = audit(self, *args, **kwargs)
        if self.repository.session.info.get("hold_write"):
            self.repository.session.flush()
            held.set()
            assert release.wait(15)
        return result

    def pause_login(self, user):
        result = issue(self, user)
        if self.repository.session.info.get("hold_login"):
            held.set()
            assert release.wait(15)
        return result

    def observe(connection, _cursor, statement, parameters, _context, _many):
        if not connection.info.get("counselor_waiter"):
            return
        if scenario == "duplicate_create" and "INSERT INTO users" in statement:
            waiting.set()
        elif "FROM users" in statement and "FOR UPDATE" in statement and data["target"] in parameters.values():
            waiting.set()

    monkeypatch.setattr(AuditService, "record", pause_audit)
    monkeypatch.setattr(AuthService, "_issue_session", pause_login)
    event.listen(mysql_test_engine, "before_cursor_execute", observe)

    def act(first):
        with Session(mysql_test_engine, expire_on_commit=False, autoflush=False) as db:
            db.execute(text("SET SESSION innodb_lock_wait_timeout=8"))
            db.connection().info["counselor_waiter"] = not first
            connection_ids.append(db.scalar(text("SELECT CONNECTION_ID()")))
            login_action = scenario == "login_first" and first or scenario == "edit_first" and not first
            db.info["hold_login"] = first and login_action
            db.info["hold_write"] = first and not login_action
            try:
                if login_action:
                    AuthService(db).login(data["old_email"], "race-password")
                    db.commit()
                    return "LOGIN"
                actor = db.get(User, data["admins"][0 if first else 1])
                if scenario == "duplicate_create":
                    AccountsService(db).create_counselor(actor, CounselorAccountCreateRequest(
                        email=data["create_email"], first_name="New", last_name="Counselor", password="race-new-password"))
                    return "CREATED"
                AccountsService(db).update_counselor(actor, data["target"], CounselorAccountUpdateRequest(
                    email=data["new_email"], first_name="First" if first else "Second", middle_name=None,
                    last_name="Edited", expected_updated_at=data["stamp"]))
                return "UPDATED"
            except AppError as exc:
                db.rollback()
                return exc.code
            finally:
                db.connection().info["counselor_waiter"] = False

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(act, True)
            try:
                assert held.wait(15)
                second = pool.submit(act, False)
                assert waiting.wait(15)
            finally:
                release.set()
            results = first.result(timeout=20), second.result(timeout=20)
        assert len(set(connection_ids)) == 2
        assert results == {
            "edit_first": ("UPDATED", "INVALID_CREDENTIALS"),
            "login_first": ("LOGIN", "UPDATED"),
            "two_edits": ("UPDATED", "USER_EDIT_CONFLICT"),
            "duplicate_create": ("CREATED", "EMAIL_ALREADY_REGISTERED"),
        }[scenario]
        with Session(mysql_test_engine) as db:
            if scenario == "duplicate_create":
                assert db.scalar(select(func.count()).select_from(User).where(User.email == data["create_email"])) == 1
                assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.actor_user_id.in_(data["admins"]),
                    AuditEvent.event_type == "counselor_account_created")) == 1
            else:
                target = db.get(User, data["target"])
                assert target.email == data["new_email"] and target.role_code == "COUNSELOR" and not target.is_deactivated
                assert db.scalar(select(func.count()).select_from(UserSession).where(UserSession.user_id == data["target"], UserSession.revoked_at.is_(None))) == 0
                assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.actor_user_id.in_(data["admins"]),
                    AuditEvent.event_type == "counselor_account_updated")) == 1
                if scenario == "two_edits":
                    assert target.first_name == "First"
    finally:
        release.set()
        event.remove(mysql_test_engine, "before_cursor_execute", observe)
