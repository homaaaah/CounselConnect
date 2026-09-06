"""Actual React/API HTTP flow using only the disposable MySQL test schema."""

import os
from pathlib import Path
from shutil import which
import socket
import subprocess
from threading import Event, Thread
import uuid

import pytest
from sqlalchemy.orm import Session
import uvicorn

from app.core.security import hash_password
from app.database import get_session
from app.main import create_app
from app.modules.accounts.models import User
from app.modules.enrollment_verification.models import EnrollmentVerification
from app.modules.enrollment_verification.service import EnrollmentVerificationService


def test_live_frontend_login_reload_approve_logout(mysql_test_engine):
    frontend = Path(__file__).resolve().parents[4] / "frontend"
    node = which("node")
    if not node or not (frontend / "node_modules" / "react-test-renderer").exists():
        pytest.skip(
            "Install frontend dependencies and Node to run the live React/API flow"
        )
    with Session(mysql_test_engine, expire_on_commit=False) as session:
        suffix = uuid.uuid4().hex
        email = f"live-counselor-{suffix}@example.edu"
        counselor = User(
            email=email,
            password_hash=hash_password("test-live-counselor-pass"),
            role_code="COUNSELOR",
            account_status="ACTIVE",
            first_name="Cora",
            last_name="Reyes",
        )
        student = User(
            email=f"live-student-{suffix}@example.edu",
            password_hash="unused",
            role_code="STUDENT",
            account_status="PENDING_VERIFICATION",
            first_name="Ana",
            last_name="Santos",
        )
        session.add_all([counselor, student])
        session.flush()
        service = EnrollmentVerificationService(session)
        verification = service.submit_cor(student.user_id, b"%PDF-live-test", "cor.pdf")
        verification_id = verification.verification_id
        file = service.repository.find_active_file(verification_id)
        stored_path = service._storage_path(file.storage_key)

    app = create_app(run_cleanup=False)

    def isolated_session():
        with Session(mysql_test_engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = isolated_session
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        config = uvicorn.Config(
            app, log_level="critical", access_log=False, lifespan="off"
        )
        server = uvicorn.Server(config)
        worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            for _ in range(250):
                if server.started:
                    break
                Event().wait(0.02)
            assert server.started, "Isolated test server failed to start"
            env = {
                **os.environ,
                "COUNSELCONNECT_TEST_API_URL": f"http://127.0.0.1:{port}/api/v1",
                "COUNSELCONNECT_TEST_COUNSELOR_EMAIL": email,
            }
            result = subprocess.run(
                [node, str(frontend / "tests" / "live-flow.cjs")],
                cwd=frontend,
                env=env,
                capture_output=True,
                text=True,
                timeout=25,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        finally:
            server.should_exit = True
            worker.join(timeout=5)
    with Session(mysql_test_engine) as session:
        assert session.get(EnrollmentVerification, verification_id).status == "APPROVED"
    assert not stored_path.exists()
