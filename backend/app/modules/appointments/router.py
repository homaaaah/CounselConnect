"""Thin scheduling HTTP transport with session/CSRF authorization."""

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
