"""profile_change repository: persistence only (no business rules)."""

from __future__ import annotations

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.profile_change.models import ProfileChangeRequest


class ProfileChangeRepository(BaseRepository[ProfileChangeRequest]):
    """Owns all profile_change-domain SQLAlchemy queries."""

    model = ProfileChangeRequest

    def find_pending_for_student(self, student_user_id: int) -> ProfileChangeRequest | None:
        """The Student's current PENDING request, if any (non-locking read)."""
        return self.session.scalar(
            select(ProfileChangeRequest)
            .where(
                ProfileChangeRequest.student_user_id == student_user_id,
                ProfileChangeRequest.status == "PENDING",
            )
            .order_by(
                ProfileChangeRequest.created_at.desc(),
                ProfileChangeRequest.change_request_id.desc(),
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )

    def lock_by_id(self, change_request_id: int) -> ProfileChangeRequest | None:
        return self.session.scalar(
            select(ProfileChangeRequest)
            .where(ProfileChangeRequest.change_request_id == change_request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def list_all(self, status: str | None = None) -> list[ProfileChangeRequest]:
        stmt = select(ProfileChangeRequest)
        if status is not None:
            stmt = stmt.where(ProfileChangeRequest.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(
                    ProfileChangeRequest.created_at.asc(),
                    ProfileChangeRequest.change_request_id.asc(),
                )
            )
        )
