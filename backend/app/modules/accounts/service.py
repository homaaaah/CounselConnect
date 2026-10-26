"""accounts service: authorization + business rules.

Public registration/reference data and narrow Superadmin Users operations.
Counselor clinical authority is unchanged; account status operations do not
read or modify clinical records.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError

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

    @staticmethod
    def _require_user_manager(actor):
        if actor.role_code != "SUPERADMIN" or actor.account_status != "ACTIVE" or actor.is_deactivated:
            raise AppError(code="FORBIDDEN_ROLE", message="Active Superadmin access is required.", status_code=403)

    def managed_users(self, actor, **filters):
        from app.modules.accounts.schemas import ManagedUserSummary
        from app.shared.pagination import ListEnvelope
        self._require_user_manager(actor)
        rows, total = self.repository.page_users(**filters)
        return ListEnvelope[ManagedUserSummary](items=[ManagedUserSummary(
            **ManagedUserSummary.model_validate(user).model_dump(exclude={"student_number"}),
            student_number=profile.student_number if profile and user.role_code == "STUDENT" else None) for user, profile in rows],
            total=total, page=filters["page"], page_size=filters["page_size"])

    def managed_user(self, actor, user_id):
        from app.modules.accounts.schemas import ManagedUserDetail
        from app.modules.cor_screening.repository import CorScreeningRepository
        self._require_user_manager(actor)
        user = self.ensure_found(self.repository.get(user_id), "USER_NOT_FOUND", "User not found.")
        profile = self.repository.find_student_profile(user_id) if user.role_code == "STUDENT" else None
        campus = self.repository.find_campus(profile.campus_id) if profile else None
        program = self.repository.find_program(profile.program_id) if profile else None
        enrolled = CorScreeningRepository(self.repository.session).find_registered_enrollment(user_id) if profile else None
        return ManagedUserDetail(**ManagedUserDetail.model_validate(user).model_dump(exclude={
            "student_number", "profile", "campus_name", "program_name", "valid_until"}),
            student_number=profile.student_number if profile else None,
            profile={field: getattr(profile, field) for field in
                     ("student_number", "campus_id", "program_id", "year_level", "section")} if profile else None,
            campus_name=campus.campus_name if campus else None, program_name=program.program_name if program else None,
            valid_until=enrolled.valid_until if enrolled else None)

    def change_user_status(self, actor, user_id, *, deactivated):
        from app.modules.auth.repository import AuthRepository
        from app.modules.audit.service import AuditService
        self._require_user_manager(actor)
        db = self.repository.session
        try:
            reviewer = self.repository.lock_user(actor.user_id)
            if reviewer is None:
                raise AppError(code="FORBIDDEN_ROLE", message="Active Superadmin access is required.", status_code=403)
            self._require_user_manager(reviewer)
            target = self.ensure_found(self.repository.lock_user(user_id), "USER_NOT_FOUND", "User not found.")
            if target.role_code not in {"STUDENT", "COUNSELOR"} or target.user_id == reviewer.user_id:
                raise AppError(code="USER_STATUS_CHANGE_FORBIDDEN", message="This account cannot be changed here.", status_code=403)
            if deactivated or target.is_deactivated:
                AuthRepository(db).revoke_all_sessions_for_user(user_id, "ACCOUNT_DISABLED")
            if target.is_deactivated != deactivated:
                previous = target.is_deactivated
                target.is_deactivated = deactivated
                AuditService(db).record(reviewer.user_id, "account_deactivated" if deactivated else "account_reactivated",
                    "user", user_id, metadata={"previous_is_deactivated": previous, "is_deactivated": deactivated})
            db.flush()
            db.commit()
        except DBAPIError:
            db.rollback()
            raise AppError(code="INTERNAL_ERROR", message="An unexpected error occurred.", status_code=500) from None
        except Exception:
            db.rollback()
            raise
        return self.managed_user(reviewer, user_id)

    # --- public self-registration (DFD 1.1 + 1.2 combined) -----------

    def register_student_with_cor(
        self, email: str, password: str, cor_content: bytes, cor_filename: str
    ):
        """One atomic registration: account + automated COR screening.

        Delegates screening to the cor_screening module (ADR-029). The account
        starts PENDING_VERIFICATION and is activated only after the Student
        confirms the extracted fields. Raises before any DB write if the COR
        is not a valid PDF or the screening tooling is unavailable.
        """
        from app.modules.cor_screening.service import CorScreeningService

        return CorScreeningService(self.repository.session).register_with_cor(
            email, password, cor_content, cor_filename
        )

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
        if identifier_owner is not None and identifier_owner.role_code in ("COUNSELOR", "GUIDANCE_STAFF", "SUPERADMIN"):
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

    def list_active_guidance_staff(self, actor):
        if actor.role_code != "COUNSELOR" or actor.account_status != "ACTIVE":
            raise AppError("FORBIDDEN_ROLE", "Only an active Counselor may view Guidance Staff.", status_code=403)
        return self.repository.list_active_guidance_staff()

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
