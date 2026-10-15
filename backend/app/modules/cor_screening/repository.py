"""cor_screening repository: persistence only (no business rules)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.cor_screening.models import CorScreening, CorScreeningFile

# Statuses that represent an in-progress (not yet decided) screening.
OPEN_STATUSES = ("PROCESSING", "AWAITING_CONFIRMATION", "NEEDS_RESUBMISSION", "FAILED")


class CorScreeningRepository(BaseRepository[CorScreening]):
    """Owns all cor_screening-domain SQLAlchemy queries."""

    model = CorScreening

    def lock_screening(self, screening_id: int) -> CorScreening | None:
        return self.session.scalar(
            select(CorScreening)
            .where(CorScreening.cor_screening_id == screening_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def student_for_screening(self, screening_id: int) -> int | None:
        return self.session.scalar(
            select(CorScreening.student_user_id).where(
                CorScreening.cor_screening_id == screening_id
            )
        )

    def find_by_token_hash(self, token_hash: bytes) -> CorScreening | None:
        """Non-locking lookup by verification-token digest (caller locks rows)."""
        return self.session.scalar(
            select(CorScreening)
            .where(CorScreening.verification_token_hash == token_hash)
            .execution_options(populate_existing=True)
        )

    def find_latest_for_student(self, student_user_id: int, *, lock: bool = False) -> CorScreening | None:
        stmt = (
            select(CorScreening)
            .where(CorScreening.student_user_id == student_user_id)
            .order_by(
                CorScreening.submitted_at.desc(),
                CorScreening.cor_screening_id.desc(),
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def latest_for_students(self, student_ids: list[int]) -> dict[int, CorScreening]:
        """Latest screening per student id, in one query (directory view)."""
        if not student_ids:
            return {}
        rows = self.session.scalars(
            select(CorScreening)
            .where(CorScreening.student_user_id.in_(student_ids))
            .order_by(
                CorScreening.student_user_id,
                CorScreening.submitted_at.desc(),
                CorScreening.cor_screening_id.desc(),
            )
        )
        latest: dict[int, CorScreening] = {}
        for row in rows:
            latest.setdefault(row.student_user_id, row)
        return latest

    def list_files_for_screening(self, screening_id: int) -> list[CorScreeningFile]:
        return list(
            self.session.scalars(
                select(CorScreeningFile)
                .where(CorScreeningFile.cor_screening_id == screening_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def find_active_file(
        self, screening_id: int, *, now: datetime | None = None, lock: bool = False
    ) -> CorScreeningFile | None:
        stmt = (
            select(CorScreeningFile)
            .where(
                CorScreeningFile.cor_screening_id == screening_id,
                CorScreeningFile.cleanup_state == "PENDING",
                CorScreeningFile.expires_at > (now or datetime.now(timezone.utc)),
            )
            .order_by(CorScreeningFile.cor_screening_file_id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def find_file_by_storage_key(self, storage_key: str) -> CorScreeningFile | None:
        return self.session.scalar(
            select(CorScreeningFile).where(CorScreeningFile.storage_key == storage_key)
        )

    def list_all(self, status: str | None = None) -> list[CorScreening]:
        stmt = select(CorScreening)
        if status is not None:
            stmt = stmt.where(CorScreening.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(CorScreening.submitted_at.desc())
            )
        )

    def list_cleanup_candidates(self, now: datetime) -> list[int]:
        """Tracked work only: expired/replaced files, failed deletes, or decided screenings."""
        return list(
            self.session.scalars(
                select(CorScreening.cor_screening_id)
                .outerjoin(
                    CorScreeningFile,
                    CorScreening.cor_screening_id == CorScreeningFile.cor_screening_id,
                )
                .where(
                    (CorScreeningFile.expires_at <= now)
                    | (CorScreeningFile.cleanup_state == "FAILED")
                    | ((CorScreening.status == "PASSED") & CorScreeningFile.cor_screening_file_id.is_not(None))
                    | (
                        CorScreening.status.in_(OPEN_STATUSES)
                        & (CorScreening.submitted_at <= now - timedelta(days=7))
                    )
                )
                .distinct()
                .order_by(CorScreening.cor_screening_id)
            )
        )
