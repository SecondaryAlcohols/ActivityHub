"""用户端报名与电子票接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.api.deps import ClientIp, CurrentUser, DbSession
from app.schemas.common import MessageResponse
from app.schemas.registration import MyRegistrations, RegistrationResult, TicketOut
from app.schemas.user import MyAttendanceItem
from app.services import profile as profile_service
from app.services import registrations as registration_service

router = APIRouter(tags=["报名"])


@router.post(
    "/events/{event_id}/registrations",
    response_model=RegistrationResult,
    status_code=status.HTTP_201_CREATED,
    summary="报名活动",
)
async def register(
    event_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> RegistrationResult:
    return await registration_service.register(session, user, event_id)


@router.delete(
    "/registrations/{registration_id}", response_model=MessageResponse, summary="取消报名"
)
async def cancel(
    registration_id: uuid.UUID, user: CurrentUser, session: DbSession, ip: ClientIp
) -> MessageResponse:
    await registration_service.cancel(session, user, registration_id, ip)
    return MessageResponse(message="已取消报名")


@router.get(
    "/me/registrations", response_model=MyRegistrations, summary="我的报名记录"
)
async def my_registrations(user: CurrentUser, session: DbSession) -> MyRegistrations:
    return await registration_service.list_my_registrations(session, user)


@router.get(
    "/me/registrations/{registration_id}/ticket",
    response_model=TicketOut,
    summary="获取电子票",
)
async def ticket(
    registration_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> TicketOut:
    return await registration_service.build_ticket(session, user, registration_id)


@router.get(
    "/me/attendance", response_model=list[MyAttendanceItem], summary="我的考勤记录"
)
async def my_attendance(user: CurrentUser, session: DbSession) -> list[MyAttendanceItem]:
    return await profile_service.my_attendance(session, user)
