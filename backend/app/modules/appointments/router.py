"""Thin scheduling HTTP transport with session/CSRF authorization."""

from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime

from app.modules.accounts.schemas import CampusResponse
from app.modules.appointments.schemas import (
    AppointmentCreateRequest,
    AppointmentMode,
    AppointmentRejectRequest,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    AppointmentStatus,
    AvailabilitySlotCreateRequest,
    AvailabilitySlotResponse,
    GuidanceOfficeUpdateRequest,
    CalendarBlockRequest, CalendarResponse,
    AvailabilityBlockCreateRequest,
    AvailabilityBlockResponse,
    WeeklyScheduleCreateRequest,
    WeeklyScheduleResponse,
)
from app.modules.appointments.service import (
    AppointmentsService,
    get_appointments_service,
)
from app.shared.dependencies import CurrentUser
from app.shared.pagination import ListEnvelope
from app.shared.responses import ErrorResponse


def private_response(response: Response):
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    tags=["appointments"],
    dependencies=[Depends(private_response)],
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {
            "model": ErrorResponse,
            "description": "Role, active-account, or CSRF denial",
        },
        404: {
            "model": ErrorResponse,
            "description": "Resource not found in caller scope",
        },
        409: {
            "model": ErrorResponse,
            "description": "Unavailable slot, schedule conflict, incompatible mode, or invalid transition",
        },
    },
)


@router.get("/weekly-schedules", response_model=list[WeeklyScheduleResponse])
def list_weekly_schedules(
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.list_weekly_schedules(actor)


@router.post("/weekly-schedules", status_code=201, response_model=WeeklyScheduleResponse)
def create_weekly_schedule(
    data: WeeklyScheduleCreateRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.create_weekly_schedule(actor, data)


@router.delete("/weekly-schedules/{weekly_schedule_id}", status_code=204)
def deactivate_weekly_schedule(
    weekly_schedule_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    service.deactivate_weekly_schedule(actor, weekly_schedule_id)


@router.get("/availability-blocks", response_model=list[AvailabilityBlockResponse])
def list_availability_blocks(
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.list_availability_blocks(actor)


@router.post("/availability-blocks", status_code=201, response_model=AvailabilityBlockResponse)
def create_availability_block(
    data: AvailabilityBlockCreateRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.create_availability_block(actor, data)


@router.delete("/availability-blocks/{availability_block_id}", status_code=204)
def delete_availability_block(
    availability_block_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    service.delete_availability_block(actor, availability_block_id)


@router.get("/calendar", response_model=CalendarResponse)
def calendar(
    actor: CurrentUser,
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    service: AppointmentsService = Depends(get_appointments_service),
):
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    return service.calendar(actor, start_date or today, end_date or today + timedelta(days=30))


@router.post("/calendar/blocks", status_code=201)
def block_calendar_date(data: CalendarBlockRequest, actor: CurrentUser,
                       service: AppointmentsService = Depends(get_appointments_service)):
    block = service.block_date(actor, data.blocked_date, data.reason)
    return {"blocked_date": block.blocked_date, "reason": block.reason}


@router.delete("/calendar/blocks/{blocked_date}", status_code=204)
def unblock_calendar_date(blocked_date: date, actor: CurrentUser,
                          service: AppointmentsService = Depends(get_appointments_service)):
    service.unblock_date(actor, blocked_date)


@router.get(
    "/availability-slots", response_model=ListEnvelope[AvailabilitySlotResponse]
)
def list_slots(
    actor: CurrentUser,
    campus_id: int | None = Query(None, gt=0),
    appointment_mode: AppointmentMode | None = None,
    starts_after: AwareDatetime | None = None,
    ends_before: AwareDatetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.list_slots(
        actor, campus_id, appointment_mode, starts_after, ends_before, page, page_size
    )


@router.post(
    "/availability-slots",
    status_code=201,
    response_model=ListEnvelope[AvailabilitySlotResponse],
)
def create_slots(
    data: AvailabilitySlotCreateRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    items = service.create_slots(actor, data)
    return dict(items=items, page=1, page_size=len(items), total=len(items))


@router.patch(
    "/campuses/{campus_id}/guidance-office-location", response_model=CampusResponse
)
def update_location(
    campus_id: int,
    data: GuidanceOfficeUpdateRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.accounts.set_guidance_office_location(
        actor, campus_id, data.guidance_office_location
    )


@router.get("/appointments", response_model=ListEnvelope[AppointmentResponse])
def list_appointments(
    actor: CurrentUser,
    status: AppointmentStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.list_appointments(actor, status, page, page_size)


@router.post("/appointments", status_code=201, response_model=AppointmentResponse)
def book(
    data: AppointmentCreateRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.book(actor, data)


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
def detail(
    appointment_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.detail(actor, appointment_id)


@router.post(
    "/appointments/{appointment_id}/confirm", response_model=AppointmentResponse
)
def confirm(
    appointment_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.transition(actor, appointment_id, "confirm")


@router.post(
    "/appointments/{appointment_id}/reject", response_model=AppointmentResponse
)
def reject(
    appointment_id: int,
    data: AppointmentRejectRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.transition(actor, appointment_id, "reject", data.rejection_note)


@router.post(
    "/appointments/{appointment_id}/cancel", response_model=AppointmentResponse
)
def cancel(
    appointment_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.transition(actor, appointment_id, "cancel")


@router.post(
    "/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse
)
def reschedule(
    appointment_id: int,
    data: AppointmentRescheduleRequest,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.reschedule(actor, appointment_id, data)


@router.post(
    "/appointments/{appointment_id}/complete", response_model=AppointmentResponse
)
def complete(
    appointment_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.transition(actor, appointment_id, "complete")


@router.post(
    "/appointments/{appointment_id}/no-show", response_model=AppointmentResponse
)
def no_show(
    appointment_id: int,
    actor: CurrentUser,
    service: AppointmentsService = Depends(get_appointments_service),
):
    return service.transition(actor, appointment_id, "no-show")
