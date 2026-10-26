"""profile_change repository: persistence only (no business rules)."""

from __future__ import annotations

from sqlalchemy import func, or_, select

from app.modules.bases import BaseRepository
from app.modules.profile_change.models import ProfileChangeRequest


class ProfileChangeRepository(BaseRepository[ProfileChangeRequest]):
    """Owns all profile_change-domain SQLAlchemy queries."""

    model = ProfileChangeRequest

    def page_for_student(
        self, student_user_id: int, *, status: str | None, page: int, page_size: int,
        root_change_request_id: int | None = None,
    ) -> tuple[list[ProfileChangeRequest], int]:
        return self.page_requests(student_user_id=student_user_id, status=status, page=page, page_size=page_size,
                                  root_change_request_id=root_change_request_id)

    def page_requests(
        self, *, status: str | None, page: int, page_size: int,
        student_user_id: int | None = None,
        root_change_request_id: int | None = None,
    ) -> tuple[list[ProfileChangeRequest], int]:
        conditions = []
        if student_user_id is not None:
            conditions.append(ProfileChangeRequest.student_user_id == student_user_id)
        if status is not None:
            conditions.append(ProfileChangeRequest.status == status)
        if root_change_request_id is not None:
            conditions.append(or_(ProfileChangeRequest.change_request_id == root_change_request_id,
                                  ProfileChangeRequest.root_change_request_id == root_change_request_id))
        total = self.session.scalar(select(func.count()).select_from(ProfileChangeRequest).where(*conditions))
        rows = list(self.session.scalars(
            select(ProfileChangeRequest).where(*conditions)
            .order_by(ProfileChangeRequest.created_at.desc(), ProfileChangeRequest.change_request_id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ))
        return rows, total

    def get_for_student(self, change_request_id: int, student_user_id: int) -> ProfileChangeRequest | None:
        return self.session.scalar(select(ProfileChangeRequest).where(
            ProfileChangeRequest.change_request_id == change_request_id,
            ProfileChangeRequest.student_user_id == student_user_id,
        ))

    def lock_pending_for_screening(self, screening_id: int) -> list[ProfileChangeRequest]:
        return list(self.session.scalars(
            select(ProfileChangeRequest).where(
                ProfileChangeRequest.cor_screening_id == screening_id,
                ProfileChangeRequest.status == "PENDING",
            ).order_by(ProfileChangeRequest.change_request_id).with_for_update()
            .execution_options(populate_existing=True)
        ))

    def find_pending_for_student(self, student_user_id: int, *, lock: bool = False) -> ProfileChangeRequest | None:
        """The Student's current PENDING request; optionally a locking current read."""
        stmt = (
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
        if lock:
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def lock_by_id(self, change_request_id: int) -> ProfileChangeRequest | None:
        return self.session.scalar(
            select(ProfileChangeRequest)
            .where(ProfileChangeRequest.change_request_id == change_request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def lock_lineage_metadata(self, student_user_id: int, root_id: int) -> list[dict]:
        return self.lineage_metadata(student_user_id, root_id, lock=True)

    def lineage_metadata(self, student_user_id: int, root_id: int, *, lock: bool = False) -> list[dict]:
        columns = (ProfileChangeRequest.change_request_id, ProfileChangeRequest.submission_version,
                   ProfileChangeRequest.previous_change_request_id, ProfileChangeRequest.root_change_request_id,
                   ProfileChangeRequest.status)
        stmt = select(*columns).where(
            ProfileChangeRequest.student_user_id == student_user_id,
            or_(ProfileChangeRequest.change_request_id == root_id, ProfileChangeRequest.root_change_request_id == root_id),
        ).order_by(ProfileChangeRequest.change_request_id)
        if lock:
            stmt = stmt.with_for_update()
        return [dict(row) for row in self.session.execute(stmt).mappings()]

    def has_successor(self, change_request_id: int, *, lock: bool = True) -> bool:
        stmt = select(ProfileChangeRequest.change_request_id).where(
            ProfileChangeRequest.previous_change_request_id == change_request_id,
        ).limit(1)
        if lock:
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt) is not None
