"""Session record and private document authorization/state regressions."""

import io
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.exceptions import AppError
from app.core.security import hash_password
from app.modules.accounts.models import Campus, StudentProfile, User
from app.modules.appointments.schemas import (
    AppointmentCreateRequest,
    AvailabilitySlotCreateRequest,
    SessionRecordUpdateRequest,
)
from app.modules.appointments.service import AppointmentsService
from app.modules.audit.models import AuditEvent
from app.modules.messaging.models import Conversation


@pytest.fixture()
def context(db_session, academic_references):
    campus_id, program_id = academic_references
    campus = db_session.get(Campus, campus_id)
    campus.guidance_office_location = "Guidance Office, Room 201"
    users = []
    for index, role in enumerate(["COUNSELOR", "COUNSELOR", "STUDENT", "STUDENT"]):
        user = User(
            email=f"records-{index}@example.edu",
            password_hash=hash_password("synthetic-test-pass"),
            first_name=f"Test{index}",
            last_name="Records",
            role_code=role,
            account_status="ACTIVE",
        )
        db_session.add(user)
        db_session.flush()
        if role == "STUDENT":
            db_session.add(
                StudentProfile(
                    user_id=user.user_id,
                    student_number=f"REC-{index}",
                    campus_id=campus_id,
                    program_id=program_id,
                    year_level=1,
                    section="A",
                )
            )
        users.append(user)
    db_session.flush()
    counselor, other_counselor, student, other_student = users
    service = AppointmentsService(db_session)
    start = datetime.now(timezone.utc).replace(second=0, microsecond=0) + timedelta(days=2)
    slot = service.create_slots(
        counselor,
        AvailabilitySlotCreateRequest(
            campus_id=campus.campus_id,
            delivery_mode="BOTH",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            slot_duration_minutes=60,
        ),
    )[0]
    appointment = service.book(
        student,
        AppointmentCreateRequest(
            availability_slot_id=slot.slot_id,
            appointment_mode="ONLINE",
            concern_categories=["ACADEMIC_PROBLEM"],
        ),
    )
    service.transition(counselor, appointment.appointment_id, "confirm")
    return SimpleNamespace(
        service=service,
        counselor=counselor,
        other_counselor=other_counselor,
        student=student,
        other_student=other_student,
        appointment=appointment,
    )


def record_payload(**overrides):
    values = {
        "notepad": "draft scratch",
        "presenting_concern": "Academic stress",
        "session_summary": "Student described workload pressure.",
        "intervention": "Explored coping plan.",
        "plan": "Follow up in two weeks.",
        "follow_up_on": None,
    }
    values.update(overrides)
    return SessionRecordUpdateRequest(**values)


def error_code(fn):
    with pytest.raises(AppError) as exc:
        fn()
    return exc.value.code


def start_appointment(service, appointment_id):
    """Move the reserved slot into the past so outcome actions are allowed."""
    appointment = service.repository.get(appointment_id)
    slot = service.repository.find_slot(appointment.availability_slot_id)
    slot.starts_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    slot.ends_at = slot.starts_at + timedelta(hours=1)
    service.repository.session.flush()
    return appointment


def pdf_bytes(padding=0):
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n" + b" " * padding


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "green").save(buffer, format="PNG")
    return buffer.getvalue()


def test_draft_is_counselor_only_and_final_assessment_reaches_student(context):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    saved = service.save_session_record(
        counselor, appointment.appointment_id, record_payload()
    )
    assert saved.record_id is not None
    assert saved.notepad == "draft scratch"

    assert error_code(lambda: service.get_session_record(
        student, appointment.appointment_id
    )) == "RECORD_NOT_FOUND"

    finalized = service.finalize_session_record(counselor, appointment.appointment_id)
    assert finalized.status == "FINAL"

    assert error_code(lambda: service.get_session_record(
        student, appointment.appointment_id
    )) == "RECORD_NOT_FOUND"

    appointment = service.repository.get(appointment.appointment_id)
    appointment.status = "COMPLETED"
    service.repository.session.flush()
    as_student = service.get_session_record(student, appointment.appointment_id)
    assert as_student.notepad is None
    assert as_student.presenting_concern == "Academic stress"
    assert as_student.status == "FINAL"

    as_counselor = service.get_session_record(counselor, appointment.appointment_id)
    assert as_counselor.notepad == "draft scratch"


def test_completed_appointment_with_a_draft_stays_hidden(context):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    service.save_session_record(counselor, appointment.appointment_id, record_payload())
    appointment = service.repository.get(appointment.appointment_id)
    appointment.status = "COMPLETED"
    service.repository.session.flush()
    assert error_code(lambda: service.get_session_record(
        student, appointment.appointment_id
    )) == "RECORD_NOT_FOUND"


def test_finalize_requires_fields_locks_edits_and_reopen_allows_completed(context):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload(plan=""))
    assert error_code(lambda: service.finalize_session_record(
        counselor, appointment_id
    )) == "RECORD_INCOMPLETE"

    service.save_session_record(counselor, appointment_id, record_payload())
    service.finalize_session_record(counselor, appointment_id)
    assert error_code(lambda: service.save_session_record(
        counselor, appointment_id, record_payload(notepad="new")
    )) == "RECORD_FINALIZED"

    confirmed = service.get_session_record(counselor, appointment_id)
    assert confirmed.can_reopen is True

    assert service.reopen_session_record(counselor, appointment_id).status == "DRAFT"
    service.save_session_record(counselor, appointment_id, record_payload())
    service.finalize_session_record(counselor, appointment_id)
    appointment = service.repository.get(appointment_id)
    appointment.status = "COMPLETED"
    service.repository.session.flush()

    completed = service.get_session_record(counselor, appointment_id)
    assert completed.can_reopen is True
    assert service.reopen_session_record(counselor, appointment_id).status == "DRAFT"
    assert error_code(lambda: service.get_session_record(
        student, appointment_id
    )) == "RECORD_NOT_FOUND"

    events = {
        event.event_type
        for event in service.repository.session.scalars(select(AuditEvent))
    }
    assert "session_record_finalized" in events
    assert "session_record_reopened" in events


def test_mark_done_finalizes_and_completes_atomically(context, db_session):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())
    start_appointment(service, appointment_id)
    conversation = Conversation(
        student_user_id=student.user_id,
        counselor_user_id=counselor.user_id,
        appointment_id=appointment_id,
        conversation_type="APPOINTMENT",
        status="OPEN",
    )
    db_session.add(conversation)
    db_session.flush()
    row = service.repository.get(appointment_id)
    row.conversation_id = conversation.conversation_id
    db_session.flush()

    completed = service.mark_session_done(counselor, appointment_id)

    assert completed.status == "COMPLETED"
    row = service.repository.get(appointment_id)
    assert row.status == "COMPLETED"
    assert service.repository.find_slot(row.availability_slot_id).status == "AVAILABLE"
    assert conversation.status == "CLOSED"
    assert conversation.closure_reason == "COUNSELOR_OUTCOME"
    record = service.repository.session_record(appointment_id)
    assert record.status == "FINAL" and record.finalized_at is not None

    as_student = service.get_session_record(student, appointment_id)
    assert as_student.status == "FINAL"
    assert as_student.notepad is None
    assert as_student.presenting_concern == "Academic stress"
    assert service.list_session_documents(student, appointment_id) == []

    events = [event.event_type for event in db_session.scalars(select(AuditEvent))]
    assert events.count("session_record_finalized") == 1
    assert events.count("appointment_completed") == 1


def test_mark_done_http_contract(context, db_client):
    service, counselor, appointment = (
        context.service,
        context.counselor,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())
    start_appointment(service, appointment_id)
    path = f"/api/v1/appointments/{appointment_id}/mark-done"

    login = db_client.post(
        "/api/v1/auth/login",
        json={"identifier": counselor.email, "password": "synthetic-test-pass"},
    )
    assert login.status_code == 200, login.text
    assert db_client.post(path).status_code == 403
    response = db_client.post(path, headers={"X-CSRF-Token": login.json()["csrf_token"]})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert "capabilities" in body
    assert response.headers["cache-control"] == "no-store"
    assert service.repository.session_record(appointment_id).status == "FINAL"


def test_mark_done_requires_a_saved_complete_record(context, db_session):
    service, counselor, appointment = (
        context.service,
        context.counselor,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    start_appointment(service, appointment_id)

    assert error_code(lambda: service.mark_session_done(
        counselor, appointment_id
    )) == "RECORD_NOT_SAVED"

    service.save_session_record(counselor, appointment_id, record_payload(plan=""))
    with pytest.raises(AppError) as incomplete:
        service.mark_session_done(counselor, appointment_id)
    assert incomplete.value.code == "RECORD_INCOMPLETE"
    assert incomplete.value.details == {"fields": ["plan"]}

    row = service.repository.get(appointment_id)
    assert row.status == "CONFIRMED"
    assert service.repository.session_record(appointment_id).status == "DRAFT"
    events = {event.event_type for event in db_session.scalars(select(AuditEvent))}
    assert "session_record_finalized" not in events
    assert "appointment_completed" not in events


def test_mark_done_requires_started_confirmed_and_assigned_counselor(context, db_session):
    service, counselor, other_counselor, student, appointment = (
        context.service,
        context.counselor,
        context.other_counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())

    assert error_code(lambda: service.mark_session_done(
        counselor, appointment_id
    )) == "SESSION_NOT_STARTED"
    row = service.repository.get(appointment_id)
    assert row.status == "CONFIRMED"
    assert service.repository.find_slot(row.availability_slot_id).status == "RESERVED"
    assert service.repository.session_record(appointment_id).status == "DRAFT"

    assert error_code(lambda: service.mark_session_done(
        student, appointment_id
    )) == "FORBIDDEN_ROLE"
    assert error_code(lambda: service.mark_session_done(
        other_counselor, appointment_id
    )) == "APPOINTMENT_NOT_FOUND"

    start_appointment(service, appointment_id)
    service.transition(counselor, appointment_id, "no-show")
    assert error_code(lambda: service.mark_session_done(
        counselor, appointment_id
    )) == "INVALID_APPOINTMENT_TRANSITION"
    assert service.repository.get(appointment_id).status == "NO_SHOW"
    events = {event.event_type for event in db_session.scalars(select(AuditEvent))}
    assert "appointment_completed" not in events


def test_mark_done_with_a_final_record_does_not_duplicate_the_finalize_audit(
    context, db_session
):
    service, counselor, appointment = (
        context.service,
        context.counselor,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())
    service.finalize_session_record(counselor, appointment_id)
    start_appointment(service, appointment_id)

    assert service.mark_session_done(counselor, appointment_id).status == "COMPLETED"
    events = [event.event_type for event in db_session.scalars(select(AuditEvent))]
    assert events.count("session_record_finalized") == 1
    assert events.count("appointment_completed") == 1


@pytest.mark.parametrize("action,target", [("no-show", "NO_SHOW"), ("complete", "COMPLETED")])
def test_outcome_without_mark_done_does_not_finalize(context, db_session, action, target):
    service, counselor, appointment = (
        context.service,
        context.counselor,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())
    start_appointment(service, appointment_id)

    assert service.transition(counselor, appointment_id, action).status == target
    assert service.repository.session_record(appointment_id).status == "DRAFT"
    events = {event.event_type for event in db_session.scalars(select(AuditEvent))}
    assert "session_record_finalized" not in events


def test_reopen_completed_record_keeps_files_and_refinalize_restores_student_view(
    context,
):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    service.save_session_record(counselor, appointment_id, record_payload())
    start_appointment(service, appointment_id)
    service.upload_session_document(counselor, appointment_id, pdf_bytes(), "notes.pdf")
    service.mark_session_done(counselor, appointment_id)

    assert service.get_session_record(student, appointment_id).status == "FINAL"
    assert len(service.list_session_documents(student, appointment_id)) == 1

    assert service.reopen_session_record(counselor, appointment_id).status == "DRAFT"
    assert error_code(lambda: service.get_session_record(
        student, appointment_id
    )) == "RECORD_NOT_FOUND"
    assert len(service.list_session_documents(student, appointment_id)) == 1

    service.finalize_session_record(counselor, appointment_id)
    assert service.get_session_record(student, appointment_id).status == "FINAL"


def test_only_assigned_participants_reach_the_record(context):
    service, other_counselor, other_student, appointment = (
        context.service,
        context.other_counselor,
        context.other_student,
        context.appointment,
    )
    assert error_code(lambda: service.get_session_record(
        other_counselor, appointment.appointment_id
    )) == "APPOINTMENT_NOT_FOUND"
    assert error_code(lambda: service.get_session_record(
        other_student, appointment.appointment_id
    )) == "APPOINTMENT_NOT_FOUND"


def test_documents_validate_round_trip_and_authorize_deletes(context):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    appointment = service.repository.get(appointment_id)
    appointment.status = "COMPLETED"
    service.repository.session.flush()

    assert error_code(lambda: service.upload_session_document(
        counselor, appointment_id, b"hello", "notes.txt"
    )) == "SESSION_FILE_TYPE_INVALID"
    assert error_code(lambda: service.upload_session_document(
        counselor, appointment_id, b"not a pdf", "file.pdf"
    )) == "SESSION_FILE_INVALID"

    uploaded = service.upload_session_document(
        student, appointment_id, pdf_bytes(), "referral.pdf"
    )
    assert uploaded.original_filename == "referral.pdf"
    assert uploaded.can_delete is True

    documents = service.list_session_documents(counselor, appointment_id)
    assert [document.document_id for document in documents] == [uploaded.document_id]

    content, mime_type, filename = service.download_session_document(
        counselor, appointment_id, uploaded.document_id
    )
    assert content == pdf_bytes()
    assert mime_type == "application/pdf"
    assert filename == "referral.pdf"

    counselor_file = service.upload_session_document(
        counselor, appointment_id, png_bytes(), "assessment.png"
    )
    assert error_code(lambda: service.delete_session_document(
        student, appointment_id, counselor_file.document_id
    )) == "DOCUMENT_DELETE_FORBIDDEN"

    service.delete_session_document(counselor, appointment_id, counselor_file.document_id)
    assert error_code(lambda: service.download_session_document(
        counselor, appointment_id, counselor_file.document_id
    )) == "DOCUMENT_NOT_FOUND"


def test_student_files_wait_until_completed_but_counselor_can_upload(context):
    service, counselor, student, appointment = (
        context.service,
        context.counselor,
        context.student,
        context.appointment,
    )
    appointment_id = appointment.appointment_id
    counselor_file = service.upload_session_document(
        counselor, appointment_id, pdf_bytes(), "counselor.pdf"
    )

    assert error_code(lambda: service.list_session_documents(
        student, appointment_id
    )) == "DOCUMENT_ACCESS_CLOSED"
    assert error_code(lambda: service.download_session_document(
        student, appointment_id, counselor_file.document_id
    )) == "DOCUMENT_ACCESS_CLOSED"
    assert error_code(lambda: service.upload_session_document(
        student, appointment_id, pdf_bytes(), "student.pdf"
    )) == "DOCUMENT_ACCESS_CLOSED"

    appointment = service.repository.get(appointment_id)
    appointment.status = "COMPLETED"
    service.repository.session.flush()
    listed = service.list_session_documents(student, appointment_id)
    assert [document.document_id for document in listed] == [counselor_file.document_id]


def test_document_upload_requires_confirmed_or_completed_appointment(context):
    service, counselor, appointment = (
        context.service,
        context.counselor,
        context.appointment,
    )
    service.transition(counselor, appointment.appointment_id, "cancel")
    assert error_code(lambda: service.upload_session_document(
        counselor, appointment.appointment_id, pdf_bytes(), "late.pdf"
    )) == "DOCUMENT_UPLOAD_CLOSED"
