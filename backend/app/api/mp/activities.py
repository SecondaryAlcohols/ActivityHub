from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_attendee, get_optional_attendee
from app.db import get_db
from app.models.attendee import Attendee
from app.schemas.common import ApiResponse, Page
from app.schemas.mp import MpActivityDetail, MpActivityItem
from app.schemas.registration import RegistrationCreate, RegistrationOut
from app.services import mp_views, registration_service

router = APIRouter(prefix="/mp/activities", tags=["小程序活动"])


@router.get("", response_model=ApiResponse[Page[MpActivityItem]])
async def list_activities(
    tab: Literal["all", "upcoming", "ongoing", "past"] = Query(default="all"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    activities, total = await registration_service.list_published_activities(
        db,
        tab=None if tab == "all" else tab,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=Page(
            items=[mp_views.activity_item(activity) for activity in activities],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/{activity_id}", response_model=ApiResponse[MpActivityDetail])
async def get_activity(
    activity_id: int,
    attendee: Attendee | None = Depends(get_optional_attendee),
    db: AsyncSession = Depends(get_db),
):
    activity = await registration_service.get_published_activity(db, activity_id)
    registration = None
    if attendee is not None:
        registration = await registration_service.find_registration(
            db, activity.id, attendee.id
        )

    can_signup, reason = registration_service.compute_signup_state(
        activity, registration, datetime.now()
    )
    return ApiResponse(
        data=mp_views.activity_detail(
            activity, registration, can_signup, reason
        )
    )


@router.post(
    "/{activity_id}/registrations", response_model=ApiResponse[RegistrationOut]
)
async def create_registration(
    activity_id: int,
    payload: RegistrationCreate,
    request: Request,
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    registration = await registration_service.create_registration(
        db,
        activity_id=activity_id,
        attendee=attendee,
        answers=payload.answers,
        ip=ip,
    )
    return ApiResponse(data=RegistrationOut.model_validate(registration))
