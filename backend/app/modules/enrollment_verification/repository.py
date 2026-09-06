"""enrollment_verification module: COR (registration form) review workflow.

DFD 1.2/1.3 + docs/REGISTRATION_VERIFICATION.md:
- The current COR PDF is the ONLY enrollment evidence (anti-troll proof).
- Stored privately + temporarily (7-day TTL), deleted after decision.
- Reviewer approves or rejects with a required comment; applicant is
  notified by email; approval activates the student account with a
  valid_until window.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.modules.bases import BaseRepository
from app.modules.enrollment_verification.models import (
    EnrollmentVerification,
    EnrollmentVerificationFile,
)


class EnrollmentVerificationRepository(BaseRepository[EnrollmentVerification]):
    """Owns all verification-domain SQLAlchemy queries."""

    model = EnrollmentVerification

    def lock_verification(self, verification_id: int) -> EnrollmentVerification | None:
        return self.session.scalar(
            select(EnrollmentVerification)
            .where(EnrollmentVerification.verification_id == verification_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def student_for_verification(self, verification_id: int) -> int | None:
        return self.session.scalar(
            select(EnrollmentVerification.student_user_id).where(
                EnrollmentVerification.verification_id == verification_id
            )
        )

    def find_file(self, file_id: int) -> EnrollmentVerificationFile | None:
        return self.session.get(EnrollmentVerificationFile, file_id)

    def list_files_for_verification(
        self, verification_id: int
    ) -> list[EnrollmentVerificationFile]:
        return list(
            self.session.scalars(
                select(EnrollmentVerificationFile)
                .where(EnrollmentVerificationFile.verification_id == verification_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def find_latest_for_student(
        self, student_user_id: int
    ) -> EnrollmentVerification | None:
        return self.session.scalar(
            select(EnrollmentVerification)
            .where(EnrollmentVerification.student_user_id == student_user_id)
            .order_by(
                EnrollmentVerification.submitted_at.desc(),
                EnrollmentVerification.verification_id.desc(),
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def list_pending(self) -> list[EnrollmentVerification]:
        """Pending queue ordered oldest-first (fairness)."""
        return list(
            self.session.scalars(
                select(EnrollmentVerification)
                .where(EnrollmentVerification.status == "PENDING")
                .where(
                    EnrollmentVerification.submitted_at
                    > datetime.now(timezone.utc) - timedelta(days=7)
                )
                .where(
                    select(EnrollmentVerificationFile.file_id)
                    .where(
                        EnrollmentVerificationFile.verification_id
                        == EnrollmentVerification.verification_id,
                        EnrollmentVerificationFile.cleanup_state == "PENDING",
                        EnrollmentVerificationFile.expires_at
                        > datetime.now(timezone.utc),
                    )
                    .exists()
                )
                .order_by(EnrollmentVerification.submitted_at.asc())
            )
        )

    def list_all(self, status: str | None = None) -> list[EnrollmentVerification]:
        """Every application (optionally filtered by status), newest-first.

        Permanent review record: decided rows keep decision_at, reviewer,
        reason/note, and valid_until. COR files themselves are purged after
        decisions per the privacy boundary.
        """
        stmt = select(EnrollmentVerification)
        if status is not None:
            stmt = stmt.where(EnrollmentVerification.status == status)
        return list(
            self.session.scalars(
                stmt.order_by(EnrollmentVerification.submitted_at.desc())
            )
        )

    def find_active_file(
        self, verification_id: int, *, now: datetime | None = None, lock: bool = False
    ) -> EnrollmentVerificationFile | None:
        stmt = (
            select(EnrollmentVerificationFile)
            .where(
                EnrollmentVerificationFile.verification_id == verification_id,
                EnrollmentVerificationFile.cleanup_state == "PENDING",
                EnrollmentVerificationFile.expires_at
                > (now or datetime.now(timezone.utc)),
            )
            .order_by(EnrollmentVerificationFile.file_id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if lock:
            stmt = stmt.with_for_update()
        return self.session.scalar(stmt)

    def find_file_by_storage_key(
        self, storage_key: str
    ) -> EnrollmentVerificationFile | None:
        return self.session.scalar(
            select(EnrollmentVerificationFile).where(
                EnrollmentVerificationFile.storage_key == storage_key
            )
        )

    def list_cleanup_candidates(self, now: datetime) -> list[int]:
        """Tracked work only: expired/replaced files, failed deletes, or decisions."""
        return list(
            self.session.scalars(
                select(EnrollmentVerification.verification_id)
                .outerjoin(
                    EnrollmentVerificationFile,
                    EnrollmentVerification.verification_id
                    == EnrollmentVerificationFile.verification_id,
                )
                .where(
                    (EnrollmentVerificationFile.expires_at <= now)
                    | (EnrollmentVerificationFile.cleanup_state == "FAILED")
                    | (
                        (EnrollmentVerification.status != "PENDING")
                        & EnrollmentVerificationFile.file_id.is_not(None)
                    )
                    | (
                        (EnrollmentVerification.status == "PENDING")
                        & (
                            EnrollmentVerification.submitted_at
                            <= now - timedelta(days=7)
                        )
                    )
                )
                .distinct()
                .order_by(EnrollmentVerification.verification_id)
            )
        )
