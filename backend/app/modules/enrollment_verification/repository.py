"""enrollment_verification module: COR (registration form) review workflow.

DFD 1.2/1.3 + docs/REGISTRATION_VERIFICATION.md:
- The current COR PDF is the ONLY enrollment evidence (anti-troll proof).
- Stored privately + temporarily (7-day TTL), deleted after decision.
- Reviewer approves or rejects with a required comment; applicant is
  notified by email; approval activates the student account with a
  valid_until window.
"""

from __future__ import annotations

import io
import os
import re
import uuid
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

    def find_file(self, file_id: int) -> EnrollmentVerificationFile | None:
        return self.session.get(EnrollmentVerificationFile, file_id)

    def list_files_for_verification(self, verification_id: int) -> list[EnrollmentVerificationFile]:
        return list(
            self.session.scalars(
                select(EnrollmentVerificationFile).where(
                    EnrollmentVerificationFile.verification_id == verification_id
                )
            )
        )

    def find_latest_for_student(self, student_user_id: int) -> EnrollmentVerification | None:
        return self.session.scalar(
            select(EnrollmentVerification)
            .where(EnrollmentVerification.student_user_id == student_user_id)
            .order_by(EnrollmentVerification.submitted_at.desc())
            .limit(1)
        )

    def list_pending(self) -> list[EnrollmentVerification]:
        """Pending queue ordered oldest-first (fairness)."""
        return list(
            self.session.scalars(
                select(EnrollmentVerification)
                .where(EnrollmentVerification.status == "PENDING")
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

    def find_active_file(self, verification_id: int) -> EnrollmentVerificationFile | None:
        return self.session.scalar(
            select(EnrollmentVerificationFile).where(
                EnrollmentVerificationFile.verification_id == verification_id,
                EnrollmentVerificationFile.cleanup_state == "PENDING",
            )
        )
