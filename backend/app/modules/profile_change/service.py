"""profile_change service: authorization + business rules (ADR-032).

A Student's requested profile edit is reviewed by an active Superadmin. The
Student's account is already active; approving applies the requested
names/year_level/section to the profile. Only an active Superadmin may list,
approve, or reject.

Cross-module reads/writes of users/student_profiles go through
AccountsRepository, matching the existing cor_screening pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.accounts.repository import AccountsRepository
from app.modules.bases import BaseService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.repository import ProfileChangeRepository
from app.modules.profile_change.schemas import (
    ChangeRequestStudentSummary,
    ProfileChangeRequestItem,
    ProfileChangeRequestResponse,
)


class ProfileChangeService(BaseService[ProfileChangeRequest]):
    """Student profile-edit request business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(ProfileChangeRepository(session))
        self.accounts = AccountsRepository(session)

    # ------------------------------------------------------- authorization

    @staticmethod
    def _require_superadmin(actor: User) -> None:
        if actor.role_code != "SUPERADMIN" or actor.account_status != "ACTIVE":
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="Only an active Superadmin may review profile edits.",
                status_code=403,
            )

    # ------------------------------------------------- creation (student)

    def create_pending(
        self,
        student: User,
        cor_screening_id: int,
        *,
        first_name: str,
        middle_name: str | None,
        last_name: str,
        year_level: int,
        section: str,
    ) -> ProfileChangeRequest:
        """Queue one PENDING request. Caller holds the Student row lock + tx."""
        existing = self.repository.find_pending_for_student(student.user_id)
        if existing is not None:
            raise AppError(
                code="CHANGE_REQUEST_PENDING",
                message="You already have an edit request awaiting review.",
                status_code=409,
            )
        values = self._validate_requested(first_name, middle_name, last_name, year_level, section)
        row = ProfileChangeRequest(
            student_user_id=student.user_id,
            cor_screening_id=cor_screening_id,
            status="PENDING",
            **values,
        )
        self.repository.add(row)
        self.repository.session.flush()
        return row

    @staticmethod
    def _validate_requested(
        first_name: str | None,
        middle_name: str | None,
        last_name: str | None,
        year_level: int | None,
        section: str | None,
    ) -> dict[str, object]:
        """Reject blank names/section and out-of-range year level (trimmed)."""
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        sect = (section or "").strip()
        if not first or not last or not sect:
            raise AppError(
                code="INVALID_PROFILE_EDIT",
                message="Name and section cannot be blank.",
                status_code=422,
            )
        try:
            year = int(year_level)
        except (TypeError, ValueError) as exc:
            raise AppError(
                code="INVALID_PROFILE_EDIT",
                message="Enter a valid year level.",
                status_code=422,
            ) from exc
        if not 1 <= year <= 10:
            raise AppError(
                code="INVALID_PROFILE_EDIT",
                message="Enter a valid year level.",
                status_code=422,
            )
        return {
            "requested_first_name": first,
            "requested_middle_name": (middle_name or "").strip() or None,
            "requested_last_name": last,
            "requested_year_level": year,
            "requested_section": sect,
        }

    def supersede_pending(self, student_user_id: int) -> ProfileChangeRequest | None:
        """Auto-reject a pending request when a new screening supersedes it.

        System decision (reviewer NULL); the caller commits.
        """
        row = self.repository.find_pending_for_student(student_user_id)
        if row is None:
            return None
        row.status = "REJECTED"
        row.decision_reason = "SUPERSEDED_BY_NEW_COR"
        row.reviewed_at = datetime.now(timezone.utc)
        return row

    # -------------------------------------------------- review (superadmin)

    def list_requests(
        self, actor: User, *, status: str | None = "PENDING"
    ) -> list[ProfileChangeRequestItem]:
        self._require_superadmin(actor)
        items: list[ProfileChangeRequestItem] = []
        for row in self.repository.list_all(status):
            student = self.accounts.get(row.student_user_id)
            if student is None:
                continue
            profile = self.accounts.find_student_profile(row.student_user_id)
            items.append(
                ProfileChangeRequestItem(
                    change_request=ProfileChangeRequestResponse.model_validate(row),
                    student=ChangeRequestStudentSummary.model_validate(student),
                    current_first_name=student.first_name,
                    current_middle_name=student.middle_name,
                    current_last_name=student.last_name,
                    current_year_level=profile.year_level if profile is not None else None,
                    current_section=profile.section if profile is not None else None,
                )
            )
        return items

    def approve(self, actor: User, change_request_id: int) -> ProfileChangeRequest:
        self._require_superadmin(actor)
        row = self._lock_request_after_student(change_request_id)
        self._require_pending(row)
        # Re-validate the stored values before applying (never trust the row).
        values = self._validate_requested(
            row.requested_first_name,
            row.requested_middle_name,
            row.requested_last_name,
            row.requested_year_level,
            row.requested_section,
        )
        student = self.accounts.get(row.student_user_id)
        profile = self.accounts.find_student_profile(row.student_user_id)
        if student is None or profile is None:
            raise AppError(
                code="CHANGE_REQUEST_NOT_APPLICABLE",
                message="This student profile is no longer available.",
                status_code=409,
            )
        student.first_name = values["requested_first_name"]
        student.middle_name = values["requested_middle_name"]
        student.last_name = values["requested_last_name"]
        profile.year_level = values["requested_year_level"]
        profile.section = values["requested_section"]
        row.status = "APPROVED"
        row.reviewed_by_user_id = actor.user_id
        row.reviewed_at = datetime.now(timezone.utc)
        self.repository.session.commit()
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            actor.user_id,
            "profile_change_approved",
            "profile_change_request",
            row.change_request_id,
        )
        return row

    def reject(
        self, actor: User, change_request_id: int, reason: str
    ) -> ProfileChangeRequest:
        self._require_superadmin(actor)
        reason = (reason or "").strip()
        if not reason:
            raise AppError(
                code="CHANGE_REQUEST_REASON_REQUIRED",
                message="A rejection reason is required.",
                status_code=422,
            )
        row = self._lock_request_after_student(change_request_id)
        self._require_pending(row)
        row.status = "REJECTED"
        row.decision_reason = reason
        row.reviewed_by_user_id = actor.user_id
        row.reviewed_at = datetime.now(timezone.utc)
        self.repository.session.commit()
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            actor.user_id,
            "profile_change_rejected",
            "profile_change_request",
            row.change_request_id,
        )
        return row

    # ----------------------------------------------------------- helpers

    def _lock_request_after_student(self, change_request_id: int) -> ProfileChangeRequest:
        """Lock the Student row first, then the request row (deadlock-free)."""
        row = self.ensure_found(
            self.repository.get(change_request_id),
            "CHANGE_REQUEST_NOT_FOUND",
            "Change request not found.",
        )
        self.accounts.lock_user(row.student_user_id)
        return self.ensure_found(
            self.repository.lock_by_id(change_request_id),
            "CHANGE_REQUEST_NOT_FOUND",
            "Change request not found.",
        )

    @staticmethod
    def _require_pending(row: ProfileChangeRequest) -> None:
        if row.status != "PENDING":
            raise AppError(
                code="CHANGE_REQUEST_NOT_PENDING",
                message="This edit request has already been decided.",
                status_code=409,
            )


def get_profile_change_service(session: Session = Depends(get_session)) -> ProfileChangeService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return ProfileChangeService(session)
