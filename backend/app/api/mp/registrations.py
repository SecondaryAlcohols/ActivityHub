from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_attendee
from app.db import get_db
from app.models.attendee import Attendee
from app.schemas.common import ApiResponse, Page
from app.schemas.mp import MpRegistrationDetail, MpRegistrationItem
from app.schemas.registration import RegistrationOut, TicketOut
from app.services import mp_views, registration_service

router = APIRouter(prefix="/mp/registrations", tags=["小程序报名"])


@router.get("", response_model=ApiResponse[Page[MpRegistrationItem]])
async def list_registrations(
    status: Literal["pending", "approved", "rejected", "cancelled"] | None = Query(
        default=None
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await registration_service.list_my_registrations(
        db,
        attendee_id=attendee.id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=Page(
            items=[
                mp_views.registration_item(registration, activity)
                for registration, activity in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{registration_id}", response_model=ApiResponse[MpRegistrationDetail])
async def get_registration(
    registration_id: int,
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    registration, activity = await registration_service.get_owned_registration(
        db, registration_id, attendee
    )
    return ApiResponse(
        data=mp_views.registration_detail(registration, activity)
    )


@router.post("/{registration_id}/cancel", response_model=ApiResponse[RegistrationOut])
async def cancel_registration(
    registration_id: int,
    request: Request,
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    registration, activity = await registration_service.get_owned_registration(
        db, registration_id, attendee
    )
    ip = request.client.host if request.client else None
    registration = await registration_service.cancel_registration(
        db,
        registration=registration,
        activity=activity,
        attendee_id=attendee.id,
        ip=ip,
    )
    return ApiResponse(data=RegistrationOut.model_validate(registration))


@router.get("/{registration_id}/ticket", response_model=ApiResponse[TicketOut])
async def get_ticket(
    registration_id: int,
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    registration, activity = await registration_service.get_owned_registration(
        db, registration_id, attendee
    )
    ticket = await registration_service.build_ticket(db, registration, activity)
    return ApiResponse(data=ticket)
