"""cor_screening service: authorization + business rules.

Automated COR verification (ADR-029):
- Registration creates a PENDING_VERIFICATION account and screens the COR PDF.
- A clean screening becomes AWAITING_CONFIRMATION; the Student confirms the
  extracted/academic fields, which activates the account with a validity
  window. Anything unreadable/mismatched requests resubmission (no human
  approval queue).
- COR bytes live only in the private store (seven-day TTL) and are deleted
  after confirmation or resubmission. Raw OCR text and raw barcode payloads
  are never persisted; only codes, scores, and a payload SHA-256 digest.
"""

from __future__ import annotations

import calendar
import hashlib
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.models import StudentProfile, User
from app.modules.accounts.repository import AccountsRepository
from app.modules.bases import BaseService
from app.modules.cor_screening import screening as engine
from app.modules.cor_screening.models import CorScreening, CorScreeningFile
from app.modules.cor_screening.repository import OPEN_STATUSES, CorScreeningRepository

PDF_MAGIC = b"%PDF"
SEVEN_DAYS = timedelta(days=7)
ACCOUNT_VALID_MONTHS = 12
RESUBMITTABLE_STATUSES = ("AWAITING_CONFIRMATION", "NEEDS_RESUBMISSION", "FAILED", "PROCESSING")
logger = logging.getLogger(__name__)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _add_months(start: datetime, months: int) -> date:
    """Calendar-month addition (clamps to the target month's last day)."""
    year = start.year + (start.month - 1 + months) // 12
    month = (start.month - 1 + months) % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_reference(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


class CorScreeningService(BaseService[CorScreening]):
    """COR screening and self-confirmation business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(CorScreeningRepository(session))
        self.accounts = AccountsRepository(session)

    # ------------------------------------------------------- registration

    def register_with_cor(
        self, email: str, password: str, content: bytes, filename: str
    ) -> tuple[User, CorScreening, str | None, str | None]:
        """Create a PENDING_VERIFICATION account and screen its COR atomically.

        Returns (user, screening, unmatched_campus_name, unmatched_program_name).
        """
        settings = get_settings()
        if not settings.cor_screening_enabled:
            raise AppError(
                code="REGISTRATION_DISABLED",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            )
        # Fail fast BEFORE creating anything if document tooling is missing.
        try:
            engine.ensure_dependencies(settings)
        except engine.ScreeningUnavailableError as exc:
            raise AppError(
                code="SCREENING_UNAVAILABLE",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            ) from exc

        self._validate_pdf(content, filename, settings.cor_max_mb)
        email = email.strip().lower()
        if self.accounts.find_user_by_email(email) is not None:
            raise AppError(
                code="EMAIL_ALREADY_REGISTERED",
                message="This email is already registered.",
                status_code=409,
            )

        storage_key = self._store_cor_bytes(content)
        started = datetime.now(timezone.utc)
        try:
            result = engine.screen_pdf(self._storage_path(storage_key), settings)
        except engine.ScreeningUnavailableError as exc:
            self._delete_cor_bytes(storage_key)
            raise AppError(
                code="SCREENING_UNAVAILABLE",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            ) from exc
        except Exception:
            self._delete_cor_bytes(storage_key)
            raise

        student_no = (result.fields.student_no or "").strip().upper()
        if student_no and not engine.STUDENT_NO_RE.match(student_no):
            student_no = ""
        if student_no and self.accounts.find_student_profile_by_number(student_no) is not None:
            self._delete_cor_bytes(storage_key)
            raise AppError(
                code="STUDENT_NUMBER_ALREADY_REGISTERED",
                message="This student number is already registered.",
                status_code=409,
            )

        first, middle, last = engine.split_name(result.fields.name)
        user = User(
            email=email,
            password_hash=_hash_password(password),
            role_code="STUDENT",
            account_status="PENDING_VERIFICATION",
            first_name=first or "",
            middle_name=middle,
            last_name=last or "",
        )
        self.accounts.add(user)
        self.repository.session.flush()

        # Persist the screening as PROCESSING (observable processing stage),
        # then resolve it in a second commit.
        screening = self._create_screening_record(
            user.user_id, storage_key, content, filename, started
        )
        try:
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            if not self._delete_cor_bytes(storage_key):
                logger.warning("cor_screening_upload_cleanup_retry_required")
            raise

        unmatched_campus, unmatched_program = self._apply_result(
            screening, result, student_no, datetime.now(timezone.utc)
        )
        try:
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            logger.warning("cor_screening_processing_finalize_retry_required")
            raise

        self._clear_pending_marker(storage_key)
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            user.user_id, "cor_screening_submitted", "cor_screening", screening.cor_screening_id
        )
        return user, screening, unmatched_campus, unmatched_program

    # ---------------------------------------------------------- confirm

    def confirm(self, actor: User, data) -> tuple[CorScreening, User, StudentProfile]:  # noqa: ANN001
        """Student confirms extracted fields; activates the account."""
        student = self._lock_student(actor)
        screening = self.repository.find_latest_for_student(student.user_id, lock=True)
        if screening is None:
            raise AppError(code="SCREENING_NOT_FOUND", message="No COR screening was found.", status_code=404)
        if screening.status != "AWAITING_CONFIRMATION":
            raise AppError(
                code="SCREENING_NOT_CONFIRMABLE",
                message="This screening is not awaiting confirmation.",
                status_code=409,
            )
        # Independently deny expired evidence even between cleanup passes.
        if as_utc(screening.submitted_at) + SEVEN_DAYS <= datetime.now(timezone.utc):
            screening.status = "FAILED"
            self.repository.session.commit()
            self._purge_cor_files(screening.cor_screening_id)
            raise AppError(
                code="SCREENING_EXPIRED",
                message="This COR screening has expired. Please upload a new COR.",
                status_code=409,
            )

        student_number = (data.student_number or "").strip().upper()
        if not engine.STUDENT_NO_RE.match(student_number):
            raise AppError(
                code="INVALID_STUDENT_NUMBER",
                message="Use your university-issued student number (e.g. 20231234-A).",
                status_code=422,
            )
        # The confirmed number must match the value the barcode validated
        # against; the field is read-only in the UI, and this blocks a crafted
        # request from activating a different student number.
        extracted_number = (screening.extracted_student_number or "").strip().upper()
        if extracted_number and extracted_number != student_number:
            raise AppError(
                code="STUDENT_NUMBER_MISMATCH",
                message="The student number must match the one on your registration form.",
                status_code=422,
            )
        self._assert_fields_match(screening, data)
        owner = self.accounts.find_student_profile_by_number(student_number)
        if owner is not None and owner.user_id != student.user_id:
            raise AppError(
                code="STUDENT_NUMBER_ALREADY_REGISTERED",
                message="This student number is already registered.",
                status_code=409,
            )

        campus = self.accounts.find_campus(data.campus_id)
        if campus is None or not campus.is_active:
            raise AppError(code="CAMPUS_NOT_FOUND", message="Campus does not exist or is inactive.", status_code=404)
        program = self.accounts.find_program(data.program_id)
        if program is None or not program.is_active:
            raise AppError(code="PROGRAM_NOT_FOUND", message="Program does not exist or is inactive.", status_code=404)

        now = datetime.now(timezone.utc)
        profile = self.accounts.find_student_profile(student.user_id)
        if profile is None:
            profile = StudentProfile(
                user_id=student.user_id,
                student_number=student_number,
                campus_id=data.campus_id,
                program_id=data.program_id,
                year_level=data.year_level,
                section=data.section,
            )
            self.repository.session.add(profile)
        else:
            profile.student_number = student_number
            profile.campus_id = data.campus_id
            profile.program_id = data.program_id
            profile.year_level = data.year_level
            profile.section = data.section

        student.first_name = data.first_name
        student.middle_name = data.middle_name
        student.last_name = data.last_name
        student.account_status = "ACTIVE"

        screening.status = "PASSED"
        screening.confirmed_at = now
        # Prefer the validity date printed on the COR when it is still in the
        # future; otherwise fall back to a 12-month default.
        extracted_valid = screening.extracted_valid_until
        screening.valid_until = (
            extracted_valid if (extracted_valid is not None and extracted_valid > now.date())
            else _add_months(now, ACCOUNT_VALID_MONTHS)
        )
        screening.extracted_student_number = student_number
        screening.extracted_first_name = data.first_name
        screening.extracted_middle_name = data.middle_name
        screening.extracted_last_name = data.last_name
        screening.extracted_campus_id = data.campus_id
        screening.extracted_program_id = data.program_id
        screening.extracted_year_level = data.year_level
        screening.extracted_section = data.section
        screening.extracted_academic_period = data.academic_period

        # Commit before deleting evidence (never delete on a failed decision).
        self.repository.session.commit()
        self._purge_cor_files(screening.cor_screening_id)
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            student.user_id, "account_activated", "user", student.user_id
        )
        return screening, student, profile

    # ----------------------------------------------------------- reject

    def reject(self, actor: User) -> CorScreening:
        """Student rejects the extracted details and must re-upload a COR."""
        student = self._lock_student(actor)
        screening = self.repository.find_latest_for_student(student.user_id, lock=True)
        if screening is None:
            raise AppError(code="SCREENING_NOT_FOUND", message="No COR screening was found.", status_code=404)
        if screening.status != "AWAITING_CONFIRMATION":
            raise AppError(
                code="SCREENING_NOT_CONFIRMABLE",
                message="This screening is not awaiting confirmation.",
                status_code=409,
            )
        screening.status = "NEEDS_RESUBMISSION"
        screening.failure_reason_code = "REJECTED_BY_STUDENT"
        screening.processed_at = datetime.now(timezone.utc)
        self.repository.session.commit()
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            student.user_id, "cor_screening_rejected", "cor_screening", screening.cor_screening_id
        )
        return screening

    # --------------------------------------------------------- resubmit

    def resubmit(self, actor: User, content: bytes, filename: str) -> CorScreening:
        settings = get_settings()
        if not settings.cor_screening_enabled:
            raise AppError(
                code="REGISTRATION_DISABLED",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            )
        try:
            engine.ensure_dependencies(settings)
        except engine.ScreeningUnavailableError as exc:
            raise AppError(
                code="SCREENING_UNAVAILABLE",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            ) from exc

        student = self._lock_student(actor)
        now = datetime.now(timezone.utc)
        latest = self.repository.find_latest_for_student(student.user_id, lock=True)

        # A fresh screening row is needed when there is no screening yet
        # (bare-registered account) or the previous enrollment expired.
        renewal = latest is not None and latest.status == "PASSED" and (
            latest.valid_until is None or latest.valid_until < now.date()
        )
        if latest is None or renewal:
            screening = CorScreening(
                student_user_id=student.user_id,
                status="PROCESSING",
                format_template_version=settings.cor_template_version,
                submitted_at=now,
            )
            self.repository.session.add(screening)
            self.repository.session.flush()
            old = None
        elif latest.status in RESUBMITTABLE_STATUSES:
            screening = latest
            old = self.repository.find_active_file(screening.cor_screening_id, lock=True)
            # Give an expired open flow a fresh seven-day window instead of
            # deleting the replacement immediately.
            if as_utc(screening.submitted_at) + SEVEN_DAYS <= now:
                screening.submitted_at = now
        else:
            raise AppError(
                code="SCREENING_NOT_CONFIRMABLE",
                message="This screening cannot be resubmitted.",
                status_code=409,
            )
        self._validate_pdf(content, filename, settings.cor_max_mb)

        storage_key = self._store_cor_bytes(content)
        try:
            result = engine.screen_pdf(self._storage_path(storage_key), settings)
        except engine.ScreeningUnavailableError as exc:
            self._delete_cor_bytes(storage_key)
            raise AppError(
                code="SCREENING_UNAVAILABLE",
                message="Registration is temporarily unavailable. Please try again later.",
                status_code=503,
            ) from exc
        except Exception:
            self._delete_cor_bytes(storage_key)
            raise

        student_no = (result.fields.student_no or "").strip().upper()
        if student_no and not engine.STUDENT_NO_RE.match(student_no):
            student_no = ""
        if student_no:
            owner = self.accounts.find_student_profile_by_number(student_no)
            if owner is not None and owner.user_id != student.user_id:
                self._delete_cor_bytes(storage_key)
                raise AppError(
                    code="STUDENT_NUMBER_ALREADY_REGISTERED",
                    message="This student number is already registered.",
                    status_code=409,
                )

        # Mark PROCESSING (observable processing stage), then finalize below.
        screening.status = "PROCESSING"
        screening.failure_reason_code = None
        screening.processed_at = None
        self.repository.session.commit()

        if old is not None:
            old.expires_at = now  # queue committed cleanup with the new file
        self._apply_result(screening, result, student_no, now)
        deadline = as_utc(screening.submitted_at) + SEVEN_DAYS
        self.repository.session.add(
            CorScreeningFile(
                cor_screening_id=screening.cor_screening_id,
                storage_key=storage_key,
                original_filename=filename,
                mime_type="application/pdf",
                size_bytes=len(content),
                sha256_hash=hashlib.sha256(content).digest(),
                expires_at=deadline,
                cleanup_state="PENDING",
            )
        )
        try:
            self.repository.session.commit()
        except Exception:
            self.repository.session.rollback()
            if not self._delete_cor_bytes(storage_key):
                logger.warning("cor_screening_upload_cleanup_retry_required")
            raise
        self._clear_pending_marker(storage_key)
        self._purge_cor_files(screening.cor_screening_id)
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            student.user_id, "cor_screening_resubmitted", "cor_screening", screening.cor_screening_id
        )
        return screening

    # ------------------------------------------------------------ reads

    def latest_for_student(self, actor: User) -> CorScreening | None:
        if actor.role_code != "STUDENT":
            raise AppError(code="FORBIDDEN_ROLE", message="Only a Student may view their screening.", status_code=403)
        return self.repository.find_latest_for_student(actor.user_id)

    def list_for_counselor(
        self, actor: User, status: str | None = None
    ) -> list[tuple[CorScreening, User, StudentProfile | None]]:
        if actor.role_code != "COUNSELOR" or actor.account_status != "ACTIVE":
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="Only an active Counselor may view screening records.",
                status_code=403,
            )
        result = []
        for screening in self.repository.list_all(status):
            student = self.accounts.get(screening.student_user_id)
            if student is not None:
                profile = self.accounts.find_student_profile(student.user_id)
                result.append((screening, student, profile))
        return result

    def list_students(
        self,
        actor: User,
        *,
        q: str | None = None,
        account_status: str | None = None,
        screening_status: str | None = None,
    ) -> list[tuple[User, StudentProfile | None, CorScreening | None]]:
        """Read-only directory: every Student with profile + latest screening.

        Accessible to an active Counselor or Superadmin (ADR-029/030).
        """
        if actor.role_code not in ("COUNSELOR", "SUPERADMIN") or actor.account_status != "ACTIVE":
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="Only an active Counselor or Superadmin may view the student directory.",
                status_code=403,
            )
        rows = self.accounts.list_students(q=q, account_status=account_status)
        latest = self.repository.latest_for_students([user.user_id for user, _ in rows])
        result = []
        for user, profile in rows:
            screening = latest.get(user.user_id)
            if screening_status and (screening.status if screening is not None else None) != screening_status:
                continue
            result.append((user, profile, screening))
        return result

    # -------------------------------------------------------- recovery

    def recover_student(
        self, actor: User, user_id: int
    ) -> tuple[User, StudentProfile | None, CorScreening | None]:
        """Superadmin recovery: reset a non-active Student's enrollment.

        The Student is returned to `PENDING_VERIFICATION` and any stuck open
        screening becomes `NEEDS_RESUBMISSION` (ADMIN_RECOVERY) so they can
        submit a fresh COR. Active accounts are not altered.
        """
        if actor.role_code != "SUPERADMIN" or actor.account_status != "ACTIVE":
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="Only an active Superadmin may recover accounts.",
                status_code=403,
            )
        target = self.accounts.lock_user(user_id)
        if target is None or target.role_code != "STUDENT":
            raise AppError(code="STUDENT_NOT_FOUND", message="Student not found.", status_code=404)
        if target.account_status == "ACTIVE":
            raise AppError(
                code="NOT_RECOVERABLE",
                message="An active account does not need recovery.",
                status_code=409,
            )
        target.account_status = "PENDING_VERIFICATION"
        latest = self.repository.find_latest_for_student(target.user_id, lock=True)
        if latest is not None and latest.status in OPEN_STATUSES:
            latest.status = "NEEDS_RESUBMISSION"
            latest.failure_reason_code = "ADMIN_RECOVERY"
            latest.processed_at = datetime.now(timezone.utc)
        self.repository.session.commit()
        profile = self.accounts.find_student_profile(target.user_id)
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            actor.user_id, "account_recovery", "user", target.user_id
        )
        return target, profile, latest

    # ------------------------------------------------------- persistence

    def _create_screening_record(
        self,
        student_user_id: int,
        storage_key: str,
        content: bytes,
        filename: str,
        started_at: datetime,
    ) -> CorScreening:
        """Insert a PROCESSING screening + its temporary file row (no decision yet)."""
        screening = CorScreening(
            student_user_id=student_user_id,
            status="PROCESSING",
            format_template_version=get_settings().cor_template_version,
            submitted_at=started_at,
            processing_started_at=started_at,
        )
        self.repository.session.add(screening)
        self.repository.session.flush()
        self.repository.session.add(
            CorScreeningFile(
                cor_screening_id=screening.cor_screening_id,
                storage_key=storage_key,
                original_filename=filename,
                mime_type="application/pdf",
                size_bytes=len(content),
                sha256_hash=hashlib.sha256(content).digest(),
                expires_at=started_at + SEVEN_DAYS,
                cleanup_state="PENDING",
            )
        )
        return screening

    def _apply_result(
        self, screening: CorScreening, result, student_no: str, now: datetime
    ) -> tuple[str | None, str | None]:
        settings = get_settings()
        status, failure = engine.derive_outcome(result, settings)
        screening.status = status
        screening.failure_reason_code = failure
        screening.format_template_version = settings.cor_template_version
        screening.format_match_score = result.format_score
        screening.extraction_confidence = result.extraction_confidence
        screening.barcode_status = result.barcode_status
        screening.barcode_symbology = result.barcode_symbology
        screening.barcode_payload_format_valid = result.barcode_format_valid
        screening.barcode_student_number_match = result.barcode_student_number_match
        screening.barcode_academic_period_match = result.barcode_academic_period_match
        screening.barcode_decode_confidence = result.barcode_decode_confidence
        screening.barcode_payload_hash = (
            hashlib.sha256(result.barcode_payload.encode()).digest()
            if result.barcode_payload
            else None
        )
        screening.validation_results_json = {
            "method": result.method,
            "format_score": result.format_score,
            "extraction_confidence": result.extraction_confidence,
            "missing_fields": list(result.missing),
            "barcode_status": result.barcode_status,
        }
        first, middle, last = engine.split_name(result.fields.name)
        screening.extracted_student_number = student_no or None
        screening.extracted_first_name = first or None
        screening.extracted_middle_name = middle
        screening.extracted_last_name = last or None
        screening.extracted_section = result.fields.section or None
        screening.extracted_academic_period = result.fields.academic_period or None
        screening.extracted_valid_until = _parse_iso_date(result.fields.valid_until)
        year = result.fields.year
        screening.extracted_year_level = int(year) if str(year).isdigit() and 1 <= int(year) <= 10 else None
        screening.processed_at = now
        campus_id, campus_matched = self._match_campus(result.fields.campus)
        program_id, program_matched = self._match_program(result.fields.course)
        screening.extracted_campus_id = campus_id
        screening.extracted_program_id = program_id
        return (
            None if campus_matched else (result.fields.campus or None),
            None if program_matched else (result.fields.course or None),
        )

    def _assert_fields_match(self, screening: CorScreening, data) -> None:  # noqa: ANN001
        """Reject a confirmation whose fields differ from the COR extraction.

        The UI renders these fields read-only; this blocks a crafted request
        from rewriting verified academic data. Only fields the COR did not
        yield (campus/program when unmatched, an absent middle name or period)
        may be supplied by the Student.
        """
        def norm(value) -> str:  # noqa: ANN001
            return re.sub(r"\s+", " ", (value or "").strip()).casefold()

        mismatches = []
        if norm(data.first_name) != norm(screening.extracted_first_name):
            mismatches.append("first_name")
        if norm(data.last_name) != norm(screening.extracted_last_name):
            mismatches.append("last_name")
        if screening.extracted_middle_name is not None and norm(data.middle_name) != norm(screening.extracted_middle_name):
            mismatches.append("middle_name")
        if screening.extracted_campus_id is not None and int(data.campus_id) != screening.extracted_campus_id:
            mismatches.append("campus_id")
        if screening.extracted_program_id is not None and int(data.program_id) != screening.extracted_program_id:
            mismatches.append("program_id")
        if screening.extracted_year_level is not None and int(data.year_level) != screening.extracted_year_level:
            mismatches.append("year_level")
        if norm(data.section) != norm(screening.extracted_section):
            mismatches.append("section")
        if screening.extracted_academic_period is not None and norm(data.academic_period) != norm(screening.extracted_academic_period):
            mismatches.append("academic_period")
        if mismatches:
            raise AppError(
                code="FIELD_MISMATCH",
                message="Some details do not match your registration form. Reload the page and try again.",
                status_code=422,
                details={"fields": mismatches},
            )

    def _match_campus(self, name: str | None) -> tuple[int | None, bool]:
        target = _normalize_reference(name)
        if not target:
            return None, False
        for campus in self.accounts.list_active_campuses():
            if _normalize_reference(campus.campus_name) == target:
                return campus.campus_id, True
        for campus in self.accounts.list_active_campuses():
            if target and target in _normalize_reference(campus.campus_name):
                return campus.campus_id, True
        return None, False

    def _match_program(self, name: str | None) -> tuple[int | None, bool]:
        target = _normalize_reference(name)
        if not target:
            return None, False
        for program in self.accounts.list_active_programs():
            if _normalize_reference(program.program_code) == target or _normalize_reference(program.program_name) == target:
                return program.program_id, True
        for program in self.accounts.list_active_programs():
            hay = f"{_normalize_reference(program.program_name)} {_normalize_reference(program.program_code)}"
            if target and target in hay:
                return program.program_id, True
        return None, False

    # ------------------------------------------------------------ files

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

    def _store_cor_bytes(self, content: bytes) -> str:
        root = Path(get_settings().cor_storage_root)
        key = f"cor/{uuid.uuid4().hex}.pdf"
        target = root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        # A minimal durable marker covers crashes between the filesystem write
        # and the DB commit. It contains no document data.
        target.with_suffix(".pending").touch(exist_ok=False)
        target.write_bytes(content)
        return key

    def _storage_path(self, storage_key: str) -> str:
        root = Path(get_settings().cor_storage_root).resolve()
        target = (root / storage_key).resolve()
        if not target.is_relative_to(root) or target == root:
            raise OSError("Invalid private storage key")
        return str(target)

    def _delete_cor_bytes(self, storage_key: str) -> bool:
        try:
            target = Path(self._storage_path(storage_key))
            target.unlink(missing_ok=True)
            target.with_suffix(".pending").unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _clear_pending_marker(self, storage_key: str) -> None:
        try:
            Path(self._storage_path(storage_key)).with_suffix(".pending").unlink(missing_ok=True)
        except OSError:
            logger.warning("cor_screening_upload_marker_cleanup_retry_required")

    def _purge_cor_files(self, screening_id: int) -> None:
        """Delete only committed cleanup work, retaining failed rows for retry."""
        screening = self._lock_screening(screening_id)
        now = datetime.now(timezone.utc)
        for file_row in self.repository.list_files_for_screening(screening_id):
            if (
                screening.status in ("AWAITING_CONFIRMATION", "NEEDS_RESUBMISSION", "PROCESSING", "FAILED")
                and file_row.cleanup_state == "PENDING"
                and as_utc(file_row.expires_at) > now
            ):
                continue
            if self._delete_cor_bytes(file_row.storage_key):
                self.repository.session.delete(file_row)
                logger.info("cor_screening_file_deleted file_id=%s", file_row.cor_screening_file_id)
            else:
                file_row.cleanup_state = "FAILED"
                logger.warning(
                    "cor_screening_file_cleanup_failed file_id=%s", file_row.cor_screening_file_id
                )
        self.repository.session.commit()

    def _lock_screening(self, screening_id: int) -> CorScreening:
        student_id = self.repository.student_for_screening(screening_id)
        if student_id is None:
            raise AppError(code="SCREENING_NOT_FOUND", message="Screening not found.", status_code=404)
        self.accounts.lock_user(student_id)
        return self.ensure_found(
            self.repository.lock_screening(screening_id),
            "SCREENING_NOT_FOUND",
            "Screening not found.",
        )

    def _lock_student(self, actor: User) -> User:
        student = self.ensure_found(
            self.accounts.lock_user(actor.user_id),
            "STUDENT_NOT_FOUND",
            "Student not found.",
        )
        if student.role_code != "STUDENT":
            raise AppError(code="FORBIDDEN_ROLE", message="This action is for Students only.", status_code=403)
        return student

    # ---------------------------------------------------------- cleanup

    def cleanup_due_files(self) -> None:
        now = datetime.now(timezone.utc)
        candidates = self.repository.list_cleanup_candidates(now)
        for screening_id in candidates:
            try:
                screening = self._lock_screening(screening_id)
                if (
                    screening.status in OPEN_STATUSES
                    and as_utc(screening.submitted_at) + SEVEN_DAYS <= now
                ):
                    screening.status = "FAILED"
                self.repository.session.commit()
                self._purge_cor_files(screening_id)
            except Exception:
                self.repository.session.rollback()
                logger.error(
                    "cor_screening_cleanup_retry_required cor_screening_id=%s", screening_id
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
                if self.repository.find_file_by_storage_key(key) is not None:
                    marker.unlink(missing_ok=True)
                elif not self._delete_cor_bytes(key):
                    logger.warning("cor_screening_abandoned_upload_cleanup_failed")
                else:
                    logger.info("cor_screening_abandoned_upload_deleted")
            except OSError:
                logger.warning("cor_screening_upload_marker_cleanup_failed")


def _hash_password(raw: str) -> str:
    from app.core.security import hash_password

    return hash_password(raw)


def get_cor_screening_service(session: Session = Depends(get_session)) -> CorScreeningService:
    """FastAPI dependency: Session -> Repository -> Service."""
    return CorScreeningService(session)
