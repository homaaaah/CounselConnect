"""Real Users/review/Student React components against isolated FastAPI/MySQL."""

import os
from pathlib import Path
from shutil import which
import socket
import subprocess
from threading import Event, Thread

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
import uvicorn

from app.core.security import hash_password
from app.database import get_session
from app.main import create_app
from app.modules.accounts.models import User
from app.modules.audit.models import AuditEvent
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.service import CorScreeningService
from app.modules.profile_change.models import ProfileChangeRequest
from .test_correction_decision_concurrency import committed_correction  # noqa: F401


def test_live_management_workflows(mysql_test_engine, committed_correction):
    run_management_workflows(mysql_test_engine, committed_correction)


def run_management_workflows(mysql_test_engine, committed_correction, *, script="live-management.cjs", extra_env=None):
    frontend = Path(__file__).resolve().parents[4] / "frontend"
    node = which("node")
    if not node or not (frontend / "node_modules" / "react-test-renderer").exists():
        pytest.skip("Install frontend dependencies for React/API integration")
    data = committed_correction
    with Session(mysql_test_engine) as db:
        reviewer = db.get(User, data["reviewers"][0])
        reviewer.password_hash = hash_password("synthetic-ui-pass")
        email = reviewer.email
        student_email = db.get(User, data["student"]).email
        extras = [User(email=f"ui-page-{data['student']}-{index}@example.edu", password_hash="not-a-login",
            role_code="STUDENT", account_status="ACTIVE", first_name="Synthetic", last_name="AAA Page") for index in range(21)]
        db.add_all(extras)
        db.commit()
        extra_ids = [user.user_id for user in extras]
    app = create_app(run_cleanup=False)
    def isolated_session():
        with Session(mysql_test_engine, expire_on_commit=False) as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
    app.dependency_overrides[get_session] = isolated_session
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off"))
            worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            worker.start()
            try:
                for _ in range(250):
                    if server.started:
                        break
                    Event().wait(0.02)
                assert server.started
                result = subprocess.run([node, str(frontend / "tests" / script)], cwd=frontend,
                    env={**os.environ, "COUNSELCONNECT_TEST_API_URL": f"http://127.0.0.1:{port}/api/v1",
                         "COUNSELCONNECT_TEST_MANAGER": email, "COUNSELCONNECT_TEST_STUDENT": student_email,
                         "COUNSELCONNECT_TEST_STUDENT_ID": str(data["student"]),
                         "COUNSELCONNECT_TEST_REQUEST_ID": str(data["request"]), **(extra_env or {})},
                    capture_output=True, text=True, timeout=180 if script == "browser-management.cjs" else 90)
                assert result.returncode == 0, result.stdout + result.stderr
            finally:
                server.should_exit = True
                worker.join(timeout=10)
    finally:
        with Session(mysql_test_engine) as db:
            created_counselors = list(db.scalars(select(AuditEvent.target_id).where(
                AuditEvent.actor_user_id.in_(data["reviewers"]), AuditEvent.target_type == "user",
                AuditEvent.event_type == "counselor_account_created")))
            db.execute(delete(AuditEvent).where(AuditEvent.actor_user_id.in_(data["reviewers"]),
                AuditEvent.event_type.in_(["counselor_account_created", "counselor_account_updated"])))
            if created_counselors:
                db.execute(delete(User).where(User.user_id.in_(created_counselors), User.role_code == "COUNSELOR"))
            children = list(db.scalars(select(ProfileChangeRequest).where(ProfileChangeRequest.student_user_id == data["student"],
                ProfileChangeRequest.change_request_id != data["request"]).order_by(ProfileChangeRequest.change_request_id.desc())))
            for child in children:
                keys = list(db.scalars(select(CorScreeningFile.storage_key).where(CorScreeningFile.cor_screening_id == child.cor_screening_id)))
                for key in keys:
                    assert CorScreeningService(db)._delete_cor_bytes(key)
                db.execute(delete(AuditEvent).where(AuditEvent.target_type == "profile_change_request", AuditEvent.target_id == child.change_request_id))
                db.delete(child)
                db.flush()
            db.execute(delete(AuditEvent).where(AuditEvent.event_type.in_(["account_deactivated", "account_reactivated"]), AuditEvent.target_id == data["student"]))
            db.execute(delete(User).where(User.user_id.in_(extra_ids)))
            db.commit()
