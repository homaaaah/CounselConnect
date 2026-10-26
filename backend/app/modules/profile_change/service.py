"""profile_change service: authorization + business rules (ADR-032).

A Student's requested profile edit is reviewed by an active Superadmin. The
Student's account is already active; approving applies the requested
names/year_level/section to the profile. Students read only their own status
and permitted comparisons; the review queue and decisions remain Superadmin-only.

Cross-module reads/writes of users/student_profiles go through
AccountsRepository, matching the existing cor_screening pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.exceptions import AppError
from app.database import get_session
from app.modules.accounts.models import User
from app.modules.accounts.repository import AccountsRepository
from app.modules.bases import BaseService
from app.modules.profile_change.models import ProfileChangeRequest
from app.modules.profile_change.normalization import normalize_profile_fields, normalize_text
from app.modules.profile_change.repository import ProfileChangeRepository
from app.modules.profile_change.schemas import (
    ChangeRequestStudentSummary,
    ProfileChangeRequestItem,
    ReviewProfileChangeRequestResponse,
    CorrectionRegisteredValues,
    StudentProfileChangeRequestItem,
    StudentProfileChangeRequestResponse,
    RegistrationSnapshot,
    CorrectionHistoryEntry,
    ReviewProfileChangeRequestDetail,
)
from app.shared.pagination import ListEnvelope

logger = logging.getLogger(__name__)

class ProfileChangeService(BaseService[ProfileChangeRequest]):
    """Student profile-edit request business rules."""

    def __init__(self, session: Session) -> None:
        super().__init__(ProfileChangeRepository(session))
        self.accounts = AccountsRepository(session)

    @staticmethod
    def _require_student_read(actor: User) -> None:
        if actor.role_code != "STUDENT":
            raise AppError(code="FORBIDDEN_ROLE", message="Only a Student may read their own correction status.", status_code=403)
        if actor.is_deactivated:
            raise AppError(code="ACCOUNT_DEACTIVATED", message="This account is deactivated.", status_code=403)

    def list_student_requests(
        self, actor: User, *, status: str | None, page: int, page_size: int,
        root_change_request_id: int | None = None,
    ) -> ListEnvelope[StudentProfileChangeRequestItem]:
        self._require_student_read(actor)
        if root_change_request_id is not None:
            self._history_root(actor, root_change_request_id)
        rows, total = self.repository.page_for_student(actor.user_id, status=status, page=page, page_size=page_size,
                                                      root_change_request_id=root_change_request_id)
        profile = self.accounts.find_student_profile(actor.user_id)
        return ListEnvelope[StudentProfileChangeRequestItem](
            items=[self._student_item(row, actor, profile) for row in rows],
            page=page, page_size=page_size, total=total,
        )

    def get_student_request(self, actor: User, change_request_id: int) -> StudentProfileChangeRequestItem:
        self._require_student_read(actor)
        row = self.ensure_found(
            self.repository.get_for_student(change_request_id, actor.user_id),
            "CHANGE_REQUEST_NOT_FOUND", "Change request not found.",
        )
        return self._student_item(row, actor, self.accounts.find_student_profile(actor.user_id))

    def _history_root(self, actor: User, root_id: int) -> ProfileChangeRequest:
        # Call only after the role/deactivation guard. Conceal foreign roots
        # before counting/selecting history, including malformed foreign links.
        root = (self.repository.get_for_student(root_id, actor.user_id) if actor.role_code == "STUDENT"
                else self.repository.get(root_id))
        if root is None or root.root_change_request_id is not None or root.previous_change_request_id is not None:
            raise AppError(code="CHANGE_REQUEST_NOT_FOUND", message="Change request not found.", status_code=404)
        return root

    @staticmethod
    def _snapshot(value) -> RegistrationSnapshot | None:
        if not isinstance(value, dict):
            return None
        fields = RegistrationSnapshot.model_fields
        if not fields.keys() <= value.keys():
            return None
        try:
            return RegistrationSnapshot.model_validate({field: value[field] for field in fields})
        except ValidationError:
            # Never log stored field values or validator inputs.
            return None

    def get_review_request(self, actor: User, change_request_id: int) -> ReviewProfileChangeRequestDetail:
        self._require_superadmin(actor)
        row = self.ensure_found(self.repository.get(change_request_id),
                                "CHANGE_REQUEST_NOT_FOUND", "Change request not found.")
        student = self.ensure_found(self.accounts.get(row.student_user_id),
                                    "CHANGE_REQUEST_NOT_FOUND", "Change request not found.")
        profile = self.accounts.find_student_profile(row.student_user_id)
        from app.modules.cor_screening.service import CorScreeningService

        current = {field: getattr(student, field) for field in ("first_name", "middle_name", "last_name")}
        current.update({field: getattr(profile, field) if profile else None for field in
                        ("student_number", "campus_id", "program_id", "year_level", "section")})
        current.update(CorScreeningService(self.repository.session).registered_enrollment_context(student.user_id))
        baseline = self._snapshot(row.registered_values_json)
        changed = self._student_item(row, student, profile, include_capability=False).changed_fields if baseline is not None else None
        proposal = {field: getattr(row, f"requested_{field}") for field in
                    (changed if changed is not None else ("first_name", "middle_name", "last_name", "year_level", "section"))}
        metadata = ReviewProfileChangeRequestResponse.model_validate(row)
        root_id = row.root_change_request_id or row.change_request_id
        if row.root_change_request_id is not None:
            root = self.repository.get_for_student(root_id, row.student_user_id)
            if root is None or root.previous_change_request_id is not None or root.root_change_request_id is not None:
                metadata.root_change_request_id = None
                root_id = None
        history = [CorrectionHistoryEntry.model_validate(row)]
        if row.previous_change_request_id is not None:
            previous = self.repository.get_for_student(row.previous_change_request_id, row.student_user_id)
            if (previous is not None and previous.change_request_id != row.change_request_id and root_id is not None
                    and (previous.root_change_request_id or previous.change_request_id) == root_id):
                history.append(CorrectionHistoryEntry.model_validate(previous))
            else:
                metadata.previous_change_request_id = None
        return ReviewProfileChangeRequestDetail(
            change_request=metadata, student=ChangeRequestStudentSummary.model_validate(student),
            extracted_values=self._snapshot(row.extracted_values_json), registered_values_at_submission=baseline,
            current_registered_values=RegistrationSnapshot.model_validate(current), proposed_changes=proposal,
            changed_fields=changed, history=history,
            evidence=CorScreeningService(self.repository.session).correction_evidence_status(row),
        )

    def _student_item(self, row: ProfileChangeRequest, student: User, profile, *, include_capability: bool = True) -> StudentProfileChangeRequestItem:
        proposed = {field: getattr(row, f"requested_{field}") for field in
                    ("first_name", "middle_name", "last_name", "year_level", "section")}
        baseline = None
        snapshot = row.registered_values_json
        if isinstance(snapshot, dict) and proposed.keys() <= snapshot.keys():
            try:
                baseline = CorrectionRegisteredValues.model_validate({field: snapshot[field] for field in proposed})
            except ValidationError:
                # Incomplete/invalid historical context remains unknown. Never
                # log validation inputs or invent a previous registered value.
                pass
        changed = None
        if baseline is not None:
            changed = [field for field, value in proposed.items() if
                       (value != getattr(baseline, field) if field == "year_level" else
                        normalize_text(value).casefold() != normalize_text(getattr(baseline, field)).casefold())]
        return StudentProfileChangeRequestItem(
            can_resubmit=self._can_student_resubmit(row, student, profile) if include_capability else False,
            change_request=StudentProfileChangeRequestResponse.model_validate(row),
            current_first_name=student.first_name, current_middle_name=student.middle_name,
            current_last_name=student.last_name,
            current_year_level=profile.year_level if profile is not None else None,
            current_section=profile.section if profile is not None else None,
            registered_values_at_submission=baseline, changed_fields=changed,
        )

    # ------------------------------------------------------- authorization

    @staticmethod
    def _require_superadmin(actor: User) -> None:
        if actor.role_code != "SUPERADMIN" or actor.account_status != "ACTIVE":
            raise AppError(
                code="FORBIDDEN_ROLE",
                message="Only an active Superadmin may review profile edits.",
                status_code=403,
            )
        if actor.is_deactivated:
            raise AppError(code="ACCOUNT_DEACTIVATED", message="This account is deactivated.", status_code=403)

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
        try:
            self.repository.session.flush()
        except IntegrityError as exc:
            self.repository.session.rollback()
            # MySQL identifies the violated key in 1062. Parse only that key;
            # never echo/log the SQL, duplicate value, or proposed fields.
            args = getattr(exc.orig, "args", ())
            key = str(args[1]).rsplit(" for key ", 1)[-1].strip("'`").rsplit(".", 1)[-1] if len(args) > 1 else ""
            if args and args[0] == 1062 and key == "uq_profile_change_requests_pending_student":
                raise AppError(
                    code="CHANGE_REQUEST_PENDING",
                    message="You already have an edit request awaiting review.",
                    status_code=409,
                ) from None
            raise
        return row

    @staticmethod
    def _validate_requested(
        first_name: str | None,
        middle_name: str | None,
        last_name: str | None,
        year_level: int | None,
        section: str | None,
    ) -> dict[str, object]:
        """Apply the same canonical validation used at confirmation/submission."""
        values = normalize_profile_fields(first_name, middle_name, last_name, year_level, section)
        return {f"requested_{field}": value for field, value in values.items()}

    def supersede_pending(self, student_user_id: int) -> ProfileChangeRequest | None:
        """Auto-reject a pending request when a new screening supersedes it.

        System decision (reviewer NULL); the caller commits.
        """
        row = self.repository.find_pending_for_student(student_user_id)
        if row is None:
            return None
        row = self.repository.lock_by_id(row.change_request_id)
        if row is None or row.status != "PENDING":
            return None
        if row.submission_version is not None:
            self.return_pending_for_evidence(row, "SUPERSEDED_BY_NEW_COR")
            return row
        row.status = "REJECTED"
        row.decision_reason = "SUPERSEDED_BY_NEW_COR"
        row.reviewed_at = datetime.now(timezone.utc)
        return row

    def lock_pending_for_screening(self, screening_id: int) -> list[ProfileChangeRequest]:
        """Internal cleanup entry: caller holds Student then screening locks."""
        return self.repository.lock_pending_for_screening(screening_id)

    def return_pending_for_evidence(self, row: ProfileChangeRequest, reason_code: str) -> None:
        """System evidence transition; caller holds row locks and commits."""
        if reason_code not in {"COR_EVIDENCE_EXPIRED", "COR_EVIDENCE_UNAVAILABLE", "SUPERSEDED_BY_NEW_COR"}:
            raise ValueError("Unsupported evidence return reason")
        self._require_pending(row)
        row.status = "RETURNED"
        row.reviewed_by_user_id = None
        row.reviewed_at = datetime.now(timezone.utc)
        row.decision_reason = reason_code
        from app.modules.audit.service import AuditService

        AuditService(self.repository.session).record(
            None, "profile_change_returned", "profile_change_request", row.change_request_id,
            metadata={"status": "RETURNED", "submission_version": row.submission_version,
                      "reason_code": reason_code},
        )

    # -------------------------------------------------- review (superadmin)

    def list_requests(
        self, actor: User, *, status: str | None = None, page: int = 1, page_size: int = 20,
        root_change_request_id: int | None = None,
    ) -> ListEnvelope[ProfileChangeRequestItem]:
        self._require_superadmin(actor)
        root = self._history_root(actor, root_change_request_id) if root_change_request_id is not None else None
        rows, total = self.repository.page_requests(status=status, page=page, page_size=page_size,
            root_change_request_id=root_change_request_id, student_user_id=root.student_user_id if root else None)
        items: list[ProfileChangeRequestItem] = []
        for row in rows:
            student = self.accounts.get(row.student_user_id)
            if student is None:
                continue
            profile = self.accounts.find_student_profile(row.student_user_id)
            items.append(
                ProfileChangeRequestItem(
                    change_request=ReviewProfileChangeRequestResponse.model_validate(row),
                    student=ChangeRequestStudentSummary.model_validate(student),
                    current_first_name=student.first_name,
                    current_middle_name=student.middle_name,
                    current_last_name=student.last_name,
                    current_year_level=profile.year_level if profile is not None else None,
                    current_section=profile.section if profile is not None else None,
                    changed_fields=self._student_item(row, student, profile, include_capability=False).changed_fields,
                )
            )
        return ListEnvelope[ProfileChangeRequestItem](items=items, page=page, page_size=page_size, total=total)

    def _lock_superadmin(self, actor: User) -> User:
        self._require_superadmin(actor)
        reviewer = self.accounts.lock_user(actor.user_id)
        if reviewer is None:
            raise AppError(code="FORBIDDEN_ROLE", message="Only an active Superadmin may review profile edits.", status_code=403)
        self._require_superadmin(reviewer)
        return reviewer

    def read_review_cor(self, actor: User, change_request_id: int) -> bytes:
        reviewer = self._lock_superadmin(actor)
        initial = self.ensure_found(self.repository.get(change_request_id),
                                    "CHANGE_REQUEST_NOT_FOUND", "Change request not found.")
        context = initial.student_user_id, initial.cor_screening_id
        row = self._lock_request_after_student(change_request_id)
        if (row.student_user_id, row.cor_screening_id) != context:
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The COR evidence is unavailable.",
                           details={"availability": "UNAVAILABLE", "expires_at": None}, status_code=409)
        from app.modules.cor_screening.service import CorScreeningService
        from app.modules.profile_change.schemas import CorrectionEvidenceStatus

        evidence, content = CorScreeningService(self.repository.session).inspect_correction_evidence(row, lock=True)
        self._require_superadmin(reviewer)
        if evidence["availability"] != "AVAILABLE" or content is None:
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The COR evidence is unavailable.",
                           details=CorrectionEvidenceStatus.model_validate(evidence).model_dump(mode="json"), status_code=409)
        return content

    def _require_latest_lineage(self, row: ProfileChangeRequest, *, allow_legacy: bool = False, lock: bool = True) -> None:
        def conflict():
            raise AppError(code="CHANGE_REQUEST_VERSION_CONFLICT", message="The correction lineage has changed. Reload the request.", status_code=409)

        root_id = row.root_change_request_id or row.change_request_id
        lineage = (self.repository.lock_lineage_metadata(row.student_user_id, root_id) if lock else
                   self.repository.lineage_metadata(row.student_user_id, root_id))
        by_id = {item["change_request_id"]: item for item in lineage}
        root = by_id.get(root_id)
        if (root is None or root["root_change_request_id"] is not None or root["previous_change_request_id"] is not None
                or root["submission_version"] not in (None, 1) or self.repository.has_successor(row.change_request_id, lock=lock)):
            conflict()
        if any(item["change_request_id"] != row.change_request_id and
               (row.submission_version is None or item["submission_version"] is None or item["submission_version"] >= row.submission_version)
               for item in lineage if item["change_request_id"] != root_id):
            conflict()
        current = by_id.get(row.change_request_id)
        visited = set()
        while current is not None and current["change_request_id"] != root_id:
            current_id = current["change_request_id"]
            if current_id in visited:
                conflict()
            visited.add(current_id)
            parent = by_id.get(current["previous_change_request_id"])
            if (parent is None or parent["status"] not in ("RETURNED", "REJECTED")
                    or current["submission_version"] != (parent["submission_version"] or 0) + 1):
                conflict()
            current = parent
        if (current is None or (row.change_request_id == root_id and row.submission_version != 1
                               and not (allow_legacy and row.submission_version is None))
                or set(by_id) != visited | {root_id}):
            conflict()

    def _require_registered_baseline(self, row: ProfileChangeRequest):
        baseline = self._snapshot(row.registered_values_json)
        extraction = self._snapshot(row.extracted_values_json)
        if (baseline is None or extraction is None or not normalize_text(extraction.student_number)
                or row.registered_cor_screening_id is None or baseline.valid_until is None
                or not baseline.student_number or baseline.campus_id is None or baseline.program_id is None):
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The recorded review context is unavailable.", status_code=409)
        fields = ("first_name", "middle_name", "last_name", "year_level", "section")
        try:
            registered = normalize_profile_fields(**{field: getattr(baseline, field) for field in fields})
            normalize_profile_fields(**{field: getattr(extraction, field) for field in fields})
        except AppError:
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The recorded review context is unavailable.", status_code=409) from None

        def stale():
            raise AppError(code="CHANGE_REQUEST_STALE", message="Registered information has changed. Reload the request.", status_code=409)

        student = self.accounts.get(row.student_user_id)  # already refreshed under the Student lock
        profile = self.accounts.lock_student_profile(row.student_user_id)
        if student is None or student.role_code != "STUDENT" or profile is None:
            stale()
        try:
            actual = normalize_profile_fields(student.first_name, student.middle_name, student.last_name,
                                              profile.year_level, profile.section)
        except AppError:
            stale()
        if actual != registered:
            stale()
        if any(getattr(profile, field) != getattr(baseline, field) for field in ("student_number", "campus_id", "program_id")):
            stale()
        from app.modules.cor_screening.service import CorScreeningService

        screenings = CorScreeningService(self.repository.session)
        enrollment = screenings.registered_review_context(row.student_user_id)
        proof = screenings.repository.get(row.cor_screening_id)  # already refreshed under its lock
        if (enrollment is None or enrollment["cor_screening_id"] != row.registered_cor_screening_id
                or proof is None or proof.student_user_id != row.student_user_id):
            stale()
        if proof.purpose == "REGISTRATION":
            if row.registered_cor_screening_id != row.cor_screening_id:
                stale()
        elif proof.purpose == "CORRECTION":
            # Fresh exact evidence was checked above. Keep the independent
            # enrollment/profile baseline authoritative for all applied edits.
            if not screenings._matches_correction_enrollment(row, proof, lock=True):
                stale()
        else:
            stale()
        if any(enrollment[field] != getattr(baseline, field) for field in
               ("student_number", "campus_id", "program_id", "academic_period", "valid_until")):
            stale()
        campus = self.accounts.lock_campus(profile.campus_id)
        program = self.accounts.lock_program(profile.program_id)
        if campus is None or not campus.is_active or program is None or not program.is_active:
            stale()
        try:
            email_owner = self.accounts.find_user_by_email(student.email, lock=True)
            number_owner = self.accounts.find_student_profile_by_number(profile.student_number, lock=True)
        except DBAPIError:
            self.repository.session.rollback()
            raise AppError(code="INTERNAL_ERROR", message="An unexpected error occurred.", status_code=500) from None
        if (email_owner is None or email_owner.user_id != student.user_id
                or number_owner is None or number_owner.user_id != student.user_id):
            stale()
        return student, profile

    def approve(self, actor: User, change_request_id: int, *, submission_version: int) -> ProfileChangeRequest:
        self._require_superadmin(actor)
        if type(submission_version) is not int or submission_version < 1:
            raise AppError(code="VALIDATION_ERROR", message="Request validation failed.", status_code=422)
        reviewer = self._lock_superadmin(actor)
        initial = self.ensure_found(self.repository.get(change_request_id),
                                    "CHANGE_REQUEST_NOT_FOUND", "Change request not found.")
        context = initial.student_user_id, initial.cor_screening_id
        row = self._lock_request_after_student(change_request_id)
        if (row.student_user_id, row.cor_screening_id) != context:
            raise AppError(code="CHANGE_REQUEST_STALE", message="The correction context has changed. Reload the request.", status_code=409)
        self._require_pending(row)
        if row.submission_version is None:
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="This request has unknown review context.", status_code=409)
        if row.submission_version != submission_version:
            raise AppError(code="CHANGE_REQUEST_VERSION_CONFLICT", message="The correction version has changed. Reload the request.", status_code=409)
        self._require_latest_lineage(row)
        from app.modules.cor_screening.service import CorScreeningService
        from app.modules.profile_change.schemas import CorrectionEvidenceStatus

        evidence, _content = CorScreeningService(self.repository.session).inspect_correction_evidence(row, lock=True)
        self._require_superadmin(reviewer)
        if evidence["availability"] != "AVAILABLE" or _content is None:
            if evidence["availability"] == "REPLACED" and row.registered_cor_screening_id is not None:
                enrollment = CorScreeningService(self.repository.session).registered_review_context(row.student_user_id)
                if enrollment is not None and enrollment["cor_screening_id"] != row.registered_cor_screening_id:
                    raise AppError(code="CHANGE_REQUEST_STALE", message="Registered information has changed. Reload the request.", status_code=409)
            raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The COR evidence is unavailable.",
                           details=CorrectionEvidenceStatus.model_validate(evidence).model_dump(mode="json"), status_code=409)
        # Re-validate the stored values before applying (never trust the row).
        values = self._validate_requested(
            row.requested_first_name,
            row.requested_middle_name,
            row.requested_last_name,
            row.requested_year_level,
            row.requested_section,
        )
        student, profile = self._require_registered_baseline(row)
        baseline = self._snapshot(row.registered_values_json)  # validated above
        changed = {}
        for field in ("first_name", "middle_name", "last_name", "year_level", "section"):
            value = values[f"requested_{field}"]
            original = getattr(baseline, field)
            differs = (value != original if field == "year_level" else
                       normalize_text(value).casefold() != normalize_text(original).casefold())
            if differs:
                changed[field] = value

        def require_deadline():
            from app.modules.cor_screening.service import as_utc

            expires_at = evidence["expires_at"]
            if expires_at is None or as_utc(expires_at) <= datetime.now(timezone.utc):
                status = {"availability": "EXPIRED" if expires_at is not None else "UNAVAILABLE",
                          "expires_at": expires_at}
                raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The COR evidence is unavailable.",
                    details=CorrectionEvidenceStatus.model_validate(status).model_dump(mode="json"), status_code=409)

        require_deadline()
        try:
            for field, value in changed.items():
                target = profile if field in ("year_level", "section") else student
                setattr(target, field, value)
            row.status = "APPROVED"
            row.reviewed_by_user_id = actor.user_id
            row.reviewed_at = datetime.now(timezone.utc)
            from app.modules.audit.service import AuditService

            AuditService(self.repository.session).record(
                actor.user_id, "profile_change_approved", "profile_change_request", row.change_request_id,
                metadata={"previous_status": "PENDING", "status": "APPROVED", "submission_version": row.submission_version},
            )
            # Flush the complete decision/audit before the final clock check;
            # any failure rolls back the same transaction, before file cleanup.
            self.repository.session.flush()
            require_deadline()
            self.repository.session.commit()
        except DBAPIError as exc:
            self.repository.session.rollback()
            args = getattr(exc.orig, "args", ())
            key = (str(args[1]).rsplit(" for key ", 1)[-1].strip("'`").rsplit(".", 1)[-1].strip("'`")
                   if len(args) > 1 else "")
            if isinstance(exc, IntegrityError) and args and args[0] == 1062:
                if key == "uq_student_profiles_number":
                    raise AppError(code="STUDENT_NUMBER_ALREADY_REGISTERED",
                                   message="The registered Student Number conflicts with another record.", status_code=409) from None
                if key == "uq_users_email":
                    raise AppError(code="CHANGE_REQUEST_STALE",
                                   message="Registered information has changed. Reload the request.", status_code=409) from None
            # Unknown constraints/driver failures are not mislabeled as identity
            # conflicts. Keep SQL, bound values and driver messages out of logs
            # as well as the public response.
            raise AppError(code="INTERNAL_ERROR", message="An unexpected error occurred.", status_code=500) from None
        except Exception:
            self.repository.session.rollback()
            raise
        CorScreeningService(self.repository.session).cleanup_screening_files(row.cor_screening_id)
        return row

    def return_request(
        self, actor: User, change_request_id: int, reason: str, *, submission_version: int | None,
    ) -> ProfileChangeRequest:
        self._require_superadmin(actor)
        if submission_version is not None and (type(submission_version) is not int or submission_version < 1):
            raise AppError(code="VALIDATION_ERROR", message="Request validation failed.", status_code=422)
        if not isinstance(reason, str) or len(reason.strip()) > 500:
            raise AppError(code="VALIDATION_ERROR", message="Request validation failed.", status_code=422)
        reason = reason.strip()
        if not reason:
            raise AppError(code="CHANGE_REQUEST_REASON_REQUIRED", message="Explain what must be corrected.", status_code=422)
        self._lock_superadmin(actor)
        initial = self.ensure_found(self.repository.get(change_request_id),
                                    "CHANGE_REQUEST_NOT_FOUND", "Change request not found.")
        context = initial.student_user_id, initial.cor_screening_id
        row = self._lock_request_after_student(change_request_id)
        if (row.student_user_id, row.cor_screening_id) != context:
            raise AppError(code="CHANGE_REQUEST_STALE", message="The correction context has changed. Reload the request.", status_code=409)
        self._require_pending(row)
        if row.submission_version != submission_version:
            raise AppError(code="CHANGE_REQUEST_VERSION_CONFLICT", message="The correction version has changed. Reload the request.", status_code=409)
        self._require_latest_lineage(row, allow_legacy=True)
        try:
            row.status = "RETURNED"
            row.decision_reason = reason
            row.reviewed_by_user_id = actor.user_id
            row.reviewed_at = datetime.now(timezone.utc)
            from app.modules.audit.service import AuditService

            AuditService(self.repository.session).record(
                actor.user_id, "profile_change_returned", "profile_change_request", row.change_request_id,
                metadata={"previous_status": "PENDING", "status": "RETURNED", "submission_version": row.submission_version},
            )
            self.repository.session.flush()
            self.repository.session.commit()
        except DBAPIError:
            self.repository.session.rollback()
            raise AppError(code="INTERNAL_ERROR", message="An unexpected error occurred.", status_code=500) from None
        except Exception:
            self.repository.session.rollback()
            raise
        from app.modules.cor_screening.service import CorScreeningService

        CorScreeningService(self.repository.session).cleanup_screening_files(row.cor_screening_id)
        return row

    def reject(
        self, actor: User, change_request_id: int, reason: str, *, submission_version: int | None,
    ) -> ProfileChangeRequest:
        """Compatibility alias; historical REJECTED rows remain unchanged."""
        return self.return_request(actor, change_request_id, reason, submission_version=submission_version)

    def resubmit(
        self, actor: User, change_request_id: int, *, submission_version: int | None,
        proposed_changes: str, content: bytes, filename: str,
    ) -> ProfileChangeRequest:
        """Internal atomic fresh-proof revision; not exposed by a route yet."""
        from app.modules.cor_screening.models import CorScreeningFile
        from app.modules.cor_screening.service import CorScreeningService, SEVEN_DAYS, as_utc
        from app.modules.profile_change.normalization import parse_resubmission_proposal
        from app.modules.audit.service import AuditService

        db = self.repository.session
        screenings = CorScreeningService(db)
        key = None
        committed = False
        try:
            previous, student, profile, enrollment = self.prepare_resubmission(
                actor, change_request_id, submission_version=submission_version)

            def baseline_values():
                return normalize_profile_fields(student.first_name, student.middle_name, student.last_name,
                                                profile.year_level, profile.section)

            parse_resubmission_proposal(proposed_changes, baseline=baseline_values())
            proof, digest = screenings.screen_correction_document(student,
                registered_cor_screening_id=enrollment.cor_screening_id, content=content, filename=filename)
            previous, student, profile, enrollment = self.prepare_resubmission(
                actor, change_request_id, submission_version=submission_version)
            proposed = parse_resubmission_proposal(proposed_changes, baseline=baseline_values())
            context = ProfileChangeRequest(student_user_id=student.user_id,
                registered_cor_screening_id=enrollment.cor_screening_id)
            if (hashlib.sha256(content).digest() != digest
                    or not screenings._matches_correction_enrollment(context, proof, lock=True)):
                raise AppError(code="COR_CONTEXT_MISMATCH", message="The COR must match your current registered enrollment.", status_code=422)
            deadline = as_utc(proof.submitted_at) + SEVEN_DAYS

            def require_deadline():
                if deadline <= datetime.now(timezone.utc):
                    raise AppError(code="COR_EVIDENCE_UNAVAILABLE", message="The COR evidence has expired.", status_code=409)

            require_deadline()
            key = screenings._store_cor_bytes(content)
            db.add(proof)
            db.flush()
            file = CorScreeningFile(cor_screening_id=proof.cor_screening_id, storage_key=key,
                original_filename=filename, mime_type="application/pdf", size_bytes=len(content), sha256_hash=digest,
                uploaded_at=proof.submitted_at, expires_at=deadline, cleanup_state="PENDING")
            db.add(file)
            db.flush()
            fields = ("student_number", "first_name", "middle_name", "last_name", "campus_id", "program_id",
                      "year_level", "section", "academic_period")
            extraction = {field: getattr(proof, f"extracted_{field}") for field in fields}
            extraction["valid_until"] = proof.extracted_valid_until.isoformat() if proof.extracted_valid_until else None
            row = ProfileChangeRequest(student_user_id=student.user_id, cor_screening_id=proof.cor_screening_id,
                status="PENDING", submission_version=(previous.submission_version or 0) + 1,
                previous_change_request_id=previous.change_request_id,
                root_change_request_id=previous.root_change_request_id or previous.change_request_id,
                registered_cor_screening_id=enrollment.cor_screening_id, extracted_values_json=extraction,
                registered_values_json={**baseline_values(), "student_number": profile.student_number,
                    "campus_id": profile.campus_id, "program_id": profile.program_id,
                    "academic_period": enrollment.extracted_academic_period,
                    "valid_until": enrollment.valid_until.isoformat()},
                evidence_file_id=file.cor_screening_file_id, evidence_sha256_hash=digest,
                evidence_uploaded_at=file.uploaded_at, evidence_expires_at=deadline,
                **{f"requested_{field}": value for field, value in proposed.items()})
            db.add(row)
            db.flush()
            AuditService(db).record(student.user_id, "profile_change_resubmitted", "profile_change_request",
                row.change_request_id, metadata={"status": "PENDING", "submission_version": row.submission_version})
            db.flush()
            require_deadline()
            db.commit()
            committed = True
        except DBAPIError as exc:
            db.rollback()
            args = getattr(exc.orig, "args", ())
            key_name = str(args[1]).rsplit(" for key ", 1)[-1].strip("'`").rsplit(".", 1)[-1] if len(args) > 1 else ""
            if isinstance(exc, IntegrityError) and args and args[0] == 1062 and key_name == "uq_profile_change_requests_pending_student":
                raise AppError(code="CHANGE_REQUEST_PENDING", message="You already have an edit request awaiting review.", status_code=409) from None
            raise AppError(code="INTERNAL_ERROR", message="An unexpected error occurred.", status_code=500) from None
        except Exception:
            db.rollback()
            raise
        finally:
            if key is not None and not committed:
                if not screenings._delete_cor_bytes(key):
                    logger.warning("cor_screening_upload_cleanup_retry_required")
        screenings._clear_pending_marker(key)
        return row

    # ----------------------------------------------------------- helpers

    def _can_student_resubmit(self, row: ProfileChangeRequest, student: User, profile) -> bool:
        """Nonlocking advisory read; never inspect old COR or authorize a write."""
        from app.config import get_settings
        from app.modules.cor_screening.repository import CorScreeningRepository

        if (row.student_user_id != student.user_id or student.role_code != "STUDENT"
                or student.is_deactivated or student.account_status != "ACTIVE" or profile is None
                or row.status not in {"RETURNED", "REJECTED"} or not get_settings().cor_screening_enabled):
            return False
        try:
            self._require_latest_lineage(row, allow_legacy=True, lock=False)
            normalize_profile_fields(student.first_name, student.middle_name, student.last_name,
                                     profile.year_level, profile.section)
        except AppError:
            return False
        if self.repository.find_pending_for_student(student.user_id) is not None:
            return False
        screenings = CorScreeningRepository(self.repository.session)
        enrollment = screenings.find_registered_enrollment(student.user_id)
        latest = screenings.find_latest_registration(student.user_id)
        if (enrollment is None or latest is None or latest.cor_screening_id != enrollment.cor_screening_id
                or enrollment.valid_until is None or enrollment.valid_until < datetime.now(timezone.utc).date()):
            return False
        number = normalize_text(profile.student_number).upper()
        if not number or number != normalize_text(enrollment.extracted_student_number).upper():
            return False
        for field in ("campus", "program"):
            current_id = getattr(profile, f"{field}_id")
            if current_id is None or current_id != getattr(enrollment, f"extracted_{field}_id"):
                return False
            reference = getattr(self.accounts, f"find_{field}")(current_id)
            if reference is None or not reference.is_active:
                return False
        return True

    def prepare_resubmission(
        self, actor: User, change_request_id: int, *, submission_version: int | None,
    ):
        """Internal preflight; caller must finish/recheck in the same transaction.

        Holds Student, predecessor screening/request, lineage and enrollment
        locks. Does not commit, mutate, screen uploads or advertise capability.
        """
        self._require_student_read(actor)
        student = self.ensure_found(self.accounts.lock_user(actor.user_id), "STUDENT_NOT_FOUND", "Student not found.")
        self._require_student_read(student)
        if student.account_status != "ACTIVE":
            raise AppError(code="CORRECTION_RESUBMISSION_NOT_ALLOWED", message="Current enrollment is required to resubmit a correction.", status_code=409)
        if submission_version is not None and (type(submission_version) is not int or submission_version < 1):
            raise AppError(code="VALIDATION_ERROR", message="Invalid correction version.", status_code=422)
        # Scope the first lookup before touching another Student's locks/data.
        owned = self.ensure_found(
            self.repository.get_for_student(change_request_id, student.user_id),
            "CHANGE_REQUEST_NOT_FOUND", "Change request not found.",
        )
        row = self._lock_request_after_student(owned.change_request_id)
        if row.student_user_id != student.user_id:
            raise AppError(code="CHANGE_REQUEST_NOT_FOUND", message="Change request not found.", status_code=404)
        if row.submission_version != submission_version:
            raise AppError(code="CHANGE_REQUEST_VERSION_CONFLICT", message="The correction version has changed. Reload the request.", status_code=409)
        if row.status not in {"RETURNED", "REJECTED"}:
            raise AppError(code="CORRECTION_RESUBMISSION_NOT_ALLOWED", message="Only a returned correction may be resubmitted.", status_code=409)
        self._require_latest_lineage(row, allow_legacy=True)
        if self.repository.find_pending_for_student(student.user_id, lock=True) is not None:
            raise AppError(code="CHANGE_REQUEST_PENDING", message="You already have an edit request awaiting review.", status_code=409)
        from app.modules.cor_screening.repository import CorScreeningRepository

        screenings = CorScreeningRepository(self.repository.session)
        enrollment = screenings.find_registered_enrollment(student.user_id, lock=True)
        latest = screenings.find_latest_registration(student.user_id, lock=True)
        profile = self.accounts.lock_student_profile(student.user_id)

        def unavailable():
            raise AppError(code="CORRECTION_RESUBMISSION_NOT_ALLOWED", message="Current enrollment is required to resubmit a correction.", status_code=409)

        if (profile is None or enrollment is None or latest is None
                or latest.cor_screening_id != enrollment.cor_screening_id
                or enrollment.valid_until is None or enrollment.valid_until < datetime.now(timezone.utc).date()):
            unavailable()
        number = normalize_text(profile.student_number).upper()
        if not number or number != normalize_text(enrollment.extracted_student_number).upper():
            unavailable()
        for field in ("campus", "program"):
            current_id = getattr(profile, f"{field}_id")
            if current_id is None or current_id != getattr(enrollment, f"extracted_{field}_id"):
                unavailable()
            reference = getattr(self.accounts, f"lock_{field}")(current_id)
            if reference is None or not reference.is_active:
                unavailable()
        # The next version takes its baseline from current registered values,
        # never the returned version's old extraction or unapproved proposal.
        normalize_profile_fields(student.first_name, student.middle_name, student.last_name,
                                 profile.year_level, profile.section)
        return row, student, profile, enrollment

    def _lock_request_after_student(self, change_request_id: int) -> ProfileChangeRequest:
        """Lock Student, screening, then request, matching evidence cleanup."""
        row = self.ensure_found(
            self.repository.get(change_request_id),
            "CHANGE_REQUEST_NOT_FOUND",
            "Change request not found.",
        )
        self.accounts.lock_user(row.student_user_id)
        from app.modules.cor_screening.repository import CorScreeningRepository

        CorScreeningRepository(self.repository.session).lock_screening(row.cor_screening_id)
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
