"""Real React scheduling screens against isolated FastAPI/MySQL over HTTP."""

import os
from pathlib import Path
from shutil import which
import socket
import subprocess
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
import uvicorn

from app.core.security import hash_password
from app.database import get_session
from app.main import create_app
from app.modules.accounts.models import (
    Campus,
    Department,
    Program,
    StudentProfile,
    User,
)
from app.modules.appointments.models import Appointment, AvailabilitySlot


def test_live_appointment_screens(mysql_test_engine):
    frontend = Path(__file__).resolve().parents[4] / "frontend"
    node = which("node")
    if not node or not (frontend / "node_modules" / "react-test-renderer").exists():
        pytest.skip("Install frontend dependencies for the real React/API flow")
    suffix = uuid4().hex
    with Session(mysql_test_engine, expire_on_commit=False) as db:
        campus = Campus(
            campus_name="Live appointment " + suffix,
            guidance_office_location="Synthetic Office 201",
        )
        department = Department(department_name="Live " + suffix)
        counselor = User(
            email=f"live-appt-{suffix}@example.edu",
            password_hash=hash_password("synthetic-live-pass"),
            role_code="COUNSELOR",
            account_status="ACTIVE",
            first_name="Cora",
            last_name="Live",
        )
        student = User(
            email=f"live-student-appt-{suffix}@example.edu",
            password_hash=hash_password("synthetic-live-pass"),
            role_code="STUDENT",
            account_status="ACTIVE",
            first_name="Ana",
            last_name="Live",
        )
        db.add_all([campus, department, counselor, student])
        db.flush()
        program = Program(
            department_id=department.department_id,
            program_code=suffix,
            program_name="Synthetic program",
        )
        db.add(program)
        db.flush()
        number = "APPT-" + suffix
        db.add(
            StudentProfile(
                user_id=student.user_id,
                student_number=number,
                campus_id=campus.campus_id,
                program_id=program.program_id,
                year_level=1,
                section="A",
            )
        )
        db.commit()
        counselor_id = counselor.user_id
        email = counselor.email
        campus_id = campus.campus_id
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
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="critical", access_log=False, lifespan="off")
        )
        worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            for _ in range(250):
                if server.started:
                    break
                Event().wait(0.02)
            assert server.started
            result = subprocess.run(
                [node, str(frontend / "tests" / "live-appointments.cjs")],
                cwd=frontend,
                env={
                    **os.environ,
                    "COUNSELCONNECT_TEST_API_URL": f"http://127.0.0.1:{port}/api/v1",
                    "COUNSELCONNECT_TEST_COUNSELOR_EMAIL": email,
                    "COUNSELCONNECT_TEST_STUDENT_NUMBER": number,
                    "COUNSELCONNECT_TEST_CAMPUS_ID": str(campus_id),
                },
                capture_output=True,
                text=True,
                timeout=45,
            )
            assert result.returncode == 0, result.stdout + result.stderr
        finally:
            server.should_exit = True
            worker.join(timeout=5)
    with Session(mysql_test_engine) as db:
        appointment = db.scalar(
            select(Appointment).where(Appointment.counselor_user_id == counselor_id)
        )
        assert appointment.status == "CANCELLED"
        assert appointment.meeting_location == "Synthetic Office 201"
        slots = list(
            db.scalars(
                select(AvailabilitySlot).where(
                    AvailabilitySlot.counselor_user_id == counselor_id
                )
            )
        )
        assert len(slots) == 2 and all(s.status == "AVAILABLE" for s in slots)
