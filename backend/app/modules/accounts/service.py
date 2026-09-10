"""accounts service: authorization + business rules.

Authorization model (docs/USER_ROLES.md): only COUNSELOR may manage
accounts/staff/academic corrections (arrives with ADR-P01 auth context).
Self-registration below is the open DFD 1.1 'Register Student Account' flow.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.database import get_session
from app.modules.bases import BaseService
from app.modules.accounts.models import StudentProfile, User
from app.modules.accounts.repository import AccountsRepository


class AccountsService(BaseService[User]):
    """Business rules for users, student profiles, and academic reference data."""

    def __init__(self, session: Session) -> None:
        super().__init__(AccountsRepository(session))

    # --- public self-registration (DFD 1.1 + 1.2 combined) -----------

    def register_student_with_cor(self, data, cor_content: bytes, cor_filename: str):
        """One atomic registration: account + profile + COR verification.

        Returns (user, profile, verification). Raises before any DB write
        if the COR is not a valid PDF, so a failed upload never creates a
        half-registered account.
        """
        from app.modules.enrollment_verification.service import (
            EnrollmentVerificationService,
        )

        # Fail fast on the COR before creating anything.
        cor_service = EnrollmentVerificationService(self.repository.session)
        cor_service.validate_cor(cor_content, cor_filename)

        user, profile = self.register_student(data)
        verification = cor_service.submit_cor(user.user_id, cor_content, cor_filename)
        return user, profile, verification

    def register_student(self, data) -> tuple[User, StudentProfile]:  # noqa: ANN001
        """Register a student account in PENDING_VERIFICATION state.

        Business rules (docs/REGISTRATION_VERIFICATION.md, DFD 1.1):
        - email and student_number must be unique;
        - campus/program must exist and be active;
        - account starts PENDING_VERIFICATION with no access until an
          approved COR verification (separate module).
        """
        repo = self.repository

        identifier_owner = repo.find_user_by_email(data.student_number)
        if identifier_owner is not None and identifier_owner.role_code in ("COUNSELOR", "GUIDANCE_STAFF"):
            raise AppError(
                code="INVALID_STUDENT_NUMBER",
                message="Use your university-issued student number.",
                status_code=422,
            )

        if repo.find_user_by_email(data.email) is not None:
            raise AppError(
                code="EMAIL_ALREADY_REGISTERED",
                message="This email is already registered.",
                status_code=409,
            )
        if repo.find_student_profile_by_number(data.student_number) is not None:
            raise AppError(
                code="STUDENT_NUMBER_ALREADY_REGISTERED",
                message="This student number is already registered.",
                status_code=409,
            )

        campus = repo.find_campus(data.campus_id)
        if campus is None or not campus.is_active:
            raise AppError(
                code="CAMPUS_NOT_FOUND",
                message="Campus does not exist or is inactive.",
                status_code=404,
            )
        program = repo.find_program(data.program_id)
        if program is None or not program.is_active:
            raise AppError(
                code="PROGRAM_NOT_FOUND",
                message="Program does not exist or is inactive.",
                status_code=404,
            )

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            role_code="STUDENT",
            account_status="PENDING_VERIFICATION",
            first_name=data.first_name,
            middle_name=data.middle_name,
            last_name=data.last_name,
        )
        repo.add(user)
        repo.session.flush()  # assign user_id for the profile FK

        profile = StudentProfile(
            user_id=user.user_id,
            student_number=data.student_number,
            campus_id=data.campus_id,
            program_id=data.program_id,
            year_level=data.year_level,
            section=data.section,
        )
        self.repository.session.add(profile)
        return user, profile

    # --- public reference data ----------------------------------------

    def list_active_campuses(self):
        return self.repository.list_active_campuses()

    def list_active_programs(self):
        return self.repository.list_active_programs()

    def scheduling_user(self, user_id: int, *, lock: bool = False):
        """Internal scheduling reference; callers enforce participant scope."""
        return self.repository.lock_user(user_id) if lock else self.repository.get(user_id)

    def scheduling_campus(self, campus_id: int, *, lock: bool = False):
        return self.repository.lock_campus(campus_id) if lock else self.repository.find_campus(campus_id)

    def set_guidance_office_location(self, actor, campus_id: int, location: str):
        if actor.role_code != "COUNSELOR" or actor.account_status != "ACTIVE":
            raise AppError("FORBIDDEN_ROLE", "Only an active Counselor may configure the Guidance Office.", status_code=403)
        campus = self.scheduling_campus(campus_id, lock=True)
        if campus is None or not campus.is_active:
            raise AppError("CAMPUS_NOT_FOUND", "Campus does not exist or is inactive.", status_code=404)
        campus.guidance_office_location = location
        from app.modules.audit.service import AuditService
        AuditService(self.repository.session).record(actor.user_id, "guidance_office_location_updated", "campus", campus_id)
        self.repository.session.flush()
        return campus


def get_accounts_service(session: Session = Depends(get_session)) -> AccountsService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return AccountsService(session)
