"""enrollment_verification service: authorization + business rules.

Workflow (docs/REGISTRATION_VERIFICATION.md, DFD 1.2/1.3, v4.1 note):
- The COR (registration form) PDF is the only enrollment evidence.
- File content is stored OUTSIDE MySQL in the private COR store with a
  seven-day expiry; metadata only in enrollment_verification_files.
- Reviewer (COUNSELOR — the highest authority role; there is no admin role)
  approves or rejects WITH a required comment. Approval sets account
  ACTIVE + valid_until; rejection keeps the account non-active.
- The v4.1 decision-shape invariant (moved out of DDL) is enforced here.
- COR bytes are deleted after any decision.
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.core.notifications import send_email, smtp_configured
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.accounts.repository import AccountsRepository
from app.modules.bases import BaseService
from app.modules.enrollment_verification.models import (
    EnrollmentVerification,
    EnrollmentVerificationFile,
)
from app.modules.enrollment_verification.repository import (
    EnrollmentVerificationRepository,
)

PDF_MAGIC = b"%PDF"
SEVEN_DAYS = timedelta(days=7)
# v4.1: decision-shape invariant lives here (MySQL 8 forbade the DDL CHECK).
APPROVED_NEEDS = ("decision_at", "reviewed_by_user_id", "valid_until")
REJECTED_NEEDS = ("decision_at", "reviewed_by_user_id", "reason_code")
logger = logging.getLogger(__name__)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class EnrollmentVerificationService(BaseService[EnrollmentVerification]):
    """COR verification business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(EnrollmentVerificationRepository(session))
        self.accounts = AccountsRepository(session)

    # ------------------------------------------------------------- upload

    def validate_cor(self, content: bytes, filename: str) -> None:
        """Public pre-check so callers can fail fast before any DB writes."""
        self._validate_pdf(content, filename, get_settings().cor_max_mb)

    def submit_cor(
        self, student_user_id: int, content: bytes, filename: str
    ) -> EnrollmentVerification:
        """Store a COR PDF privately and create the PENDING verification.

        Anti-troll rule: a student may have only ONE open verification — a
        new upload while PENDING/NEEDS_RESUBMISSION replaces the old file
        and stays in the same pending flow.
        """
        settings = get_settings()
        now = datetime.now(timezone.utc)
        self.ensure_found(
            self.accounts.lock_user(student_user_id),
            "STUDENT_NOT_FOUND",
            "Student not found.",
        )
        existing = self.repository.find_latest_for_student(student_user_id)

        # Validate the upload first (fail fast, no partial state).
        self._validate_pdf(content, filename, settings.cor_max_mb)

        if (
            existing is not None
            and existing.status == "PENDING"
            and as_utc(existing.submitted_at) + SEVEN_DAYS <= now
        ):
            existing.status = "EXPIRED"

        # Reuse an open flow or open a new one.
        if existing is not None and existing.status in (
            "PENDING",
            "NEEDS_RESUBMISSION",
        ):
            verification = existing
            # Replace any previous pending file.
            old = self.repository.find_active_file(
                verification.verification_id, lock=True
            )
            if old is not None:
                # Queue replacement cleanup in the SAME transaction as
                # the new file. Never delete old evidence before commit.
                old.expires_at = now
            if verification.status == "NEEDS_RESUBMISSION":
                verification.status = "PENDING"
                verification.submitted_at = now
                verification.decision_at = None
                verification.reviewed_by_user_id = None
                verification.reason_code = None
                verification.reviewer_note = None
                verification.valid_until = None
        else:
            verification = EnrollmentVerification(
                student_user_id=student_user_id,
                status="PENDING",
                submitted_at=now,
            )
            self.repository.add(verification)
            self.repository.session.flush()

        # Persist bytes in the private store (never inside MySQL).
        storage_key = self._store_cor_bytes(content, verification.verification_id)
        file_row = EnrollmentVerificationFile(
            verification_id=verification.verification_id,
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=len(content),
            expires_at=as_utc(verification.submitted_at) + SEVEN_DAYS,
            cleanup_state="PENDING",
        )
        self.repository.session.add(file_row)
        try:
            self.repository.session.flush()
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            # The on-disk marker survives if compensation fails, so the
            # cleanup worker can still find the abandoned upload by TTL.
            if not self._delete_cor_bytes(storage_key):
                logger.warning("verification_upload_cleanup_retry_required")
            raise
        self._purge_cor_files(verification.verification_id)
        try:
            self._storage_path(storage_key).with_suffix(".pending").unlink(
                missing_ok=True
            )
        except OSError:
            logger.warning("verification_upload_marker_cleanup_retry_required")
        return verification

    def _validate_pdf(self, content: bytes, filename: str, max_mb: int) -> None:
        if not filename.lower().endswith(".pdf"):
            raise AppError(
                code="COR_MUST_BE_PDF",
                message="The registration form (COR) must be a PDF file.",
                status_code=422,
            )
        if not content.startswith(PDF_MAGIC):
            raise AppError(
                code="COR_INVALID_PDF",
                message="The file does not look like a valid PDF.",
                status_code=422,
            )
        if len(content) > max_mb * 1024 * 1024:
            raise AppError(
                code="COR_TOO_LARGE",
                message=f"The COR file must be at most {max_mb} MB.",
                status_code=422,
            )

    def _store_cor_bytes(self, content: bytes, verification_id: int) -> str:
        """Write COR bytes to the private store; returns the storage key."""
        settings = get_settings()
        root = Path(settings.cor_storage_root)
        # Defense-in-depth: storage keys are random and never derived from
        # user input, so uploads cannot escape the COR root.
        key = f"cor/{uuid.uuid4().hex}.pdf"
        target = root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        # A minimal durable marker covers crashes/rollbacks between the
        # filesystem write and the DB commit. It contains no document data.
        target.with_suffix(".pending").touch(exist_ok=False)
        target.write_bytes(content)
        return key

    def _storage_path(self, storage_key: str) -> Path:
        root = Path(get_settings().cor_storage_root).resolve()
        target = (root / storage_key).resolve()
        if not target.is_relative_to(root) or target == root:
            raise OSError("Invalid private storage key")
        return target

    def _delete_cor_bytes(self, storage_key: str) -> bool:
        try:
            target = self._storage_path(storage_key)
            target.unlink(missing_ok=True)
            target.with_suffix(".pending").unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _read_cor_bytes(self, storage_key: str) -> bytes:
        target = self._storage_path(storage_key)
        if not target.is_file():
            raise AppError(
                code="COR_FILE_NOT_FOUND",
                message="The stored COR file is no longer available.",
                status_code=404,
            )
        return target.read_bytes()

    # ---------------------------------------------------------- review

    def list_pending(
        self,
    ) -> list[tuple[EnrollmentVerification, User, EnrollmentVerificationFile]]:
        """Pending queue with applicant details for the reviewer screen."""
        result = []
        for verification in self.repository.list_pending():
            student = self.accounts.get(verification.student_user_id)
            file_row = self.repository.find_active_file(verification.verification_id)
            if student is not None and file_row is not None:
                result.append((verification, student, file_row))
        return result

    def list_history(
        self, status: str | None = None
    ) -> list[tuple[EnrollmentVerification, User]]:
        """Permanent review record: all applications with applicant details.

        Decided rows show the decision, reviewer, comment, and validity.
        (COR bytes are purged after decisions per the privacy boundary, so
        history rows carry no file — by design.)
        """
        result = []
        for verification in self.repository.list_all(status):
            student = self.accounts.get(verification.student_user_id)
            if student is not None:
                result.append((verification, student))
        return result

    def get_review_detail(self, verification_id: int):
        """Full applicant detail for one verification (reviewer view)."""
        verification = self.repository.get(verification_id)
        if verification is None:
            raise AppError(
                code="VERIFICATION_NOT_FOUND",
                message="Verification request not found.",
                status_code=404,
            )
        student = self.accounts.get(verification.student_user_id)
        profile = self.accounts.find_student_profile(verification.student_user_id)
        file_row = self.repository.find_active_file(verification_id)
        return verification, student, profile, file_row

    def read_cor_pdf(self, verification_id: int) -> bytes:
        """COR bytes for the reviewer's in-app PDF preview."""
        verification = self._lock_verification(verification_id)
        self._require_current_cor(verification)
        file_row = self.repository.find_active_file(verification_id, lock=True)
        if file_row is None:
            raise AppError(
                code="COR_FILE_NOT_FOUND",
                message="The COR file was already cleaned up.",
                status_code=404,
            )
        return self._read_cor_bytes(file_row.storage_key)

    def approve(
        self, verification_id: int, reviewer_user_id: int, valid_months: int = 12
    ) -> tuple[EnrollmentVerification, bool]:
        """Approve: activate the student account with a validity window."""
        verification = self._lock_verification(verification_id)
        if verification.status != "PENDING":
            raise AppError(
                code="DECISION_ALREADY_MADE",
                message="This request was already decided.",
                status_code=409,
            )

        self._require_current_cor(verification)
        now = datetime.now(timezone.utc)
        verification.status = "APPROVED"
        verification.decision_at = now
        verification.reviewed_by_user_id = reviewer_user_id
        verification.valid_until = (now + timedelta(days=30 * valid_months)).date()
        # v4.1 invariant: APPROVED rows must carry decision+reviewer+valid_until.
        for field in APPROVED_NEEDS:
            if getattr(verification, field) is None:
                raise AppError(
                    code="VERIFICATION_INVALID_STATE", message="Invalid approval state."
                )

        # Activate the student account.
        student = self.accounts.get(verification.student_user_id)
        if student is not None:
            student.account_status = "ACTIVE"

        # Commit BEFORE the response is built: the request-scoped session
        # teardown would otherwise commit only after the response is sent,
        # and the reviewer UI's instant refresh could still see the
        # pre-decision PENDING row (observed 409-Conflict race).
        self.repository.session.commit()
        self._purge_cor_files(verification_id)

        email_queued = self._notify(verification, student, approved=True)
        return verification, email_queued

    def reject(
        self, verification_id: int, reviewer_user_id: int, reason: str
    ) -> tuple[EnrollmentVerification, bool]:
        """Reject with a REQUIRED comment; account stays non-active."""
        comment = (reason or "").strip()
        if not comment:
            raise AppError(
                code="REJECTION_COMMENT_REQUIRED",
                message="A rejection comment is required.",
                status_code=422,
            )
        verification = self._lock_verification(verification_id)
        if verification.status != "PENDING":
            raise AppError(
                code="DECISION_ALREADY_MADE",
                message="This request was already decided.",
                status_code=409,
            )

        self._require_current_cor(verification)
        verification.status = "REJECTED"
        verification.decision_at = datetime.now(timezone.utc)
        verification.reviewed_by_user_id = reviewer_user_id
        verification.reason_code = "REJECTED_BY_REVIEWER"
        verification.reviewer_note = comment[:500]
        # v4.1 invariant: REJECTED rows must carry decision+reviewer+reason.
        for field in REJECTED_NEEDS:
            if getattr(verification, field) is None:
                raise AppError(
                    code="VERIFICATION_INVALID_STATE",
                    message="Invalid rejection state.",
                )

        # Account remains PENDING_VERIFICATION (cannot sign in to services).
        student = self.accounts.get(verification.student_user_id)

        # Commit BEFORE the response is built (see approve() note: avoids
        # the post-response teardown race with the reviewer UI refresh).
        self.repository.session.commit()
        self._purge_cor_files(verification_id)

        email_queued = self._notify(
            verification, student, approved=False, comment=comment
        )
        return verification, email_queued

    def _purge_cor_files(self, verification_id: int) -> None:
        """Delete only committed cleanup work, retaining failed rows for retry."""
        verification = self._lock_verification(verification_id)
        now = datetime.now(timezone.utc)
        for file_row in self.repository.list_files_for_verification(verification_id):
            if (
                verification.status == "PENDING"
                and file_row.cleanup_state == "PENDING"
                and as_utc(file_row.expires_at) > now
            ):
                continue
            if self._delete_cor_bytes(file_row.storage_key):
                self.repository.session.delete(file_row)
                logger.info("verification_file_deleted file_id=%s", file_row.file_id)
            else:
                file_row.cleanup_state = "FAILED"
                logger.warning(
                    "verification_file_cleanup_failed file_id=%s", file_row.file_id
                )
        self.repository.session.commit()

    def _lock_verification(self, verification_id: int) -> EnrollmentVerification:
        """Consistent lock order: student, then verification, for all writers."""
        student_id = self.repository.student_for_verification(verification_id)
        if student_id is None:
            raise AppError(
                code="VERIFICATION_NOT_FOUND",
                message="Verification request not found.",
                status_code=404,
            )
        self.accounts.lock_user(student_id)
        return self.ensure_found(
            self.repository.lock_verification(verification_id),
            "VERIFICATION_NOT_FOUND",
            "Verification request not found.",
        )

    def _require_current_cor(self, verification: EnrollmentVerification) -> None:
        now = datetime.now(timezone.utc)
        if verification.status != "PENDING":
            raise AppError(
                code="COR_FILE_NOT_FOUND",
                message="The COR is no longer available.",
                status_code=404,
            )
        if as_utc(verification.submitted_at) + SEVEN_DAYS <= now:
            verification.status = "EXPIRED"
            self.repository.session.commit()
            self._purge_cor_files(verification.verification_id)
            raise AppError(
                code="VERIFICATION_EXPIRED",
                message="This COR verification has expired.",
                status_code=409,
            )
        if (
            self.repository.find_active_file(
                verification.verification_id, now=now, lock=True
            )
            is None
        ):
            raise AppError(
                code="COR_FILE_NOT_FOUND",
                message="A current COR is required.",
                status_code=404,
            )

    def cleanup_due_files(self) -> None:
        """Expire pending flows and retry tracked deletions; safe across workers."""
        now = datetime.now(timezone.utc)
        candidates = self.repository.list_cleanup_candidates(now)
        for verification_id in candidates:
            try:
                verification = self._lock_verification(verification_id)
                if (
                    verification.status == "PENDING"
                    and as_utc(verification.submitted_at) + SEVEN_DAYS <= now
                ):
                    verification.status = "EXPIRED"
                self.repository.session.commit()
                self._purge_cor_files(verification_id)
            except Exception:
                self.repository.session.rollback()
                logger.error(
                    "verification_cleanup_retry_required verification_id=%s",
                    verification_id,
                )

        self._cleanup_abandoned_uploads(now)

    def _cleanup_abandoned_uploads(self, now: datetime) -> None:
        """Reconcile only our UUID markers; never sweep unrelated files."""
        folder = Path(get_settings().cor_storage_root) / "cor"
        for marker in folder.glob("*.pending"):
            if not re.fullmatch(r"[0-9a-f]{32}", marker.stem):
                continue
            try:
                if marker.stat().st_mtime > (now - SEVEN_DAYS).timestamp():
                    continue
                key = f"cor/{marker.stem}.pdf"
                tracked = self.repository.find_file_by_storage_key(key)
                if tracked is not None:
                    # Committed uploads are handled by the DB work queue.
                    marker.unlink(missing_ok=True)
                elif not self._delete_cor_bytes(key):
                    logger.warning("verification_abandoned_upload_cleanup_failed")
                else:
                    logger.info("verification_abandoned_upload_deleted")
            except OSError:
                logger.warning("verification_upload_marker_cleanup_failed")

    # -------------------------------------------------------- notification

    def _notify(
        self, verification, student, *, approved: bool, comment: str = ""
    ) -> bool:
        """Queue the decision email in a background thread.

        Returns True when the email was queued for sending (SMTP
        configured), False when email is not configured and was skipped.
        Sending runs OFF the request path so the reviewer never waits on
        the SMTP server.
        """
        if student is None:
            return False
        subject = "CounselConnect — Registration {}".format(
            "Approved" if approved else "Rejected"
        )
        if approved:
            body = (
                "Good news! Your CounselConnect registration has been approved.\n\n"
                "You can now sign in and use the guidance services.\n"
                f"Enrollment validity expires: {verification.valid_until}.\n\n"
                "— University of Caloocan City Guidance and Counseling Office"
            )
        else:
            body = (
                "Your CounselConnect registration was reviewed and could not be approved.\n\n"
                f"Reviewer's comment: {comment}\n\n"
                "If you believe this is a mistake, please visit the Guidance and "
                "Counseling Office.\n\n"
                "— University of Caloocan City Guidance and Counseling Office"
            )

        def _send() -> None:
            try:
                send_email(to=student.email, subject=subject, body=body)
            except Exception:  # noqa: BLE001 — background send never surfaces
                pass

        if not smtp_configured():
            # Not configured: skip silently (dev machines) — report honestly.
            return False
        threading.Thread(target=_send, daemon=True).start()
        return True


def get_enrollment_verification_service(
    session: Session = Depends(get_session),
) -> EnrollmentVerificationService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return EnrollmentVerificationService(session)
