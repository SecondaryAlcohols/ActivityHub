"""用户端活动与考勤接口。"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, status

from app.api.deps import ClientIp, CurrentUser, DbSession, OptionalUser, PageQuery
from app.core.pagination import Page
from app.models.enums import AttendanceKind
from app.schemas.attendance import AttendanceContext, AttendanceResult, CheckinRequest
from app.schemas.event import EventDetail, EventListItem
from app.services import attendance as attendance_service
from app.services import events as event_service

router = APIRouter(tags=["活动"])


@router.get("/events", response_model=Page[EventListItem], summary="活动列表")
async def list_events(
    session: DbSession,
    user: OptionalUser,
    params: PageQuery,
    q: str | None = Query(None, max_length=60, description="标题/地点/主办方关键字"),
    scope: Literal["upcoming", "past", "all"] = Query("upcoming", description="时间范围"),
) -> Page[EventListItem]:
    return await event_service.list_events(session, user, q=q, scope=scope, params=params)


@router.get("/events/{event_id}", response_model=EventDetail, summary="活动详情")
async def get_event(
    event_id: uuid.UUID, session: DbSession, user: OptionalUser
) -> EventDetail:
    return await event_service.get_event_detail(session, user, event_id)


@router.get(
    "/events/{event_id}/attendance",
    response_model=AttendanceContext,
    summary="考勤中心上下文（需登录）",
)
async def attendance_context(
    event_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    ip: ClientIp,
) -> AttendanceContext:
    return await attendance_service.get_context(session, user, event_id, client_ip=ip)


@router.post(
    "/events/{event_id}/attendance/checkin",
    response_model=AttendanceResult,
    status_code=status.HTTP_201_CREATED,
    summary="提交签到",
)
async def checkin(
    event_id: uuid.UUID,
    payload: CheckinRequest,
    user: CurrentUser,
    session: DbSession,
    ip: ClientIp,
    user_agent: Annotated[str | None, Header()] = None,
) -> AttendanceResult:
    return await attendance_service.submit(
        session,
        user,
        event_id,
        AttendanceKind.CHECKIN,
        payload,
        client_ip=ip,
        user_agent=user_agent,
    )


@router.post(
    "/events/{event_id}/attendance/checkout",
    response_model=AttendanceResult,
    status_code=status.HTTP_201_CREATED,
    summary="提交签退",
)
async def checkout(
    event_id: uuid.UUID,
    payload: CheckinRequest,
    user: CurrentUser,
    session: DbSession,
    ip: ClientIp,
    user_agent: Annotated[str | None, Header()] = None,
) -> AttendanceResult:
    return await attendance_service.submit(
        session,
        user,
        event_id,
        AttendanceKind.CHECKOUT,
        payload,
        client_ip=ip,
        user_agent=user_agent,
    )
