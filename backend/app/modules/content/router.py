"""content router — public read endpoints for landing/home content.

Source structures (ERD): content_items (CMS_BLOCK / FAQ / ANNOUNCEMENT),
emergency_contacts. DFD mapping: D8 CMS/FAQ/Emergency Contact Data served by
processes 7.3/7.5 (counselor-managed) and consumed publicly per 5.6/4.6.

Counselor-only write endpoints arrive with ADR-P01 (auth context).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.content.schemas import ContentItemResponse, EmergencyContactResponse
from app.modules.content.service import ContentService, get_content_service
from app.shared.pagination import ListEnvelope, paginate

router = APIRouter(prefix="/content", tags=["content"])


def _envelope(service: ContentService, content_type: str) -> ListEnvelope[ContentItemResponse]:
    items = service.list_published(content_type)
    return paginate(
        [ContentItemResponse.model_validate(i) for i in items], page=1, page_size=max(len(items), 1)
    )


@router.get("/cms-blocks", response_model=ListEnvelope[ContentItemResponse],
            summary="Published landing/office CMS blocks")
def list_cms_blocks(service: ContentService = Depends(get_content_service)):
    return _envelope(service, "CMS_BLOCK")


@router.get("/faqs", response_model=ListEnvelope[ContentItemResponse],
            summary="Published FAQs")
def list_faqs(service: ContentService = Depends(get_content_service)):
    return _envelope(service, "FAQ")


@router.get("/announcements", response_model=ListEnvelope[ContentItemResponse],
            summary="Published announcements")
def list_announcements(service: ContentService = Depends(get_content_service)):
    return _envelope(service, "ANNOUNCEMENT")


@router.get("/emergency-contacts", response_model=ListEnvelope[EmergencyContactResponse],
            summary="Active ordered emergency contacts (SOS fallback display)")
def list_emergency_contacts(service: ContentService = Depends(get_content_service)):
    contacts = service.list_active_emergency_contacts()
    items = [EmergencyContactResponse.model_validate(c) for c in contacts]
    return paginate(items, page=1, page_size=max(len(items), 1))
