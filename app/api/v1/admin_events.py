"""管理端活动管理接口。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import ClientIp, DbSession, OrganizerUser, PageQuery
from app.core.pagination import Page
from app.models.enums import EventStatus
from app.schemas.admin import QrChallengeOut
from app.schemas.common import MessageResponse
from app.schemas.event import (
    EventAdminDetail,
    EventAdminItem,
    EventCreate,
    EventUpdate,
    PublishResponse,
    StaticCodeRotateResponse,
)
from app.services import admin_events as event_service

router = APIRouter(prefix="/admin/events", tags=["管理端 · 活动"])


@router.get("", response_model=Page[EventAdminItem], summary="我的活动列表")
async def list_events(
    session: DbSession,
    user: OrganizerUser,
    params: PageQuery,
    q: str | None = Query(None, max_length=60),
    status: EventStatus | None = Query(None),
) -> Page[EventAdminItem]:
    return await event_service.list_events(session, user, q=q, status=status, params=params)


@router.post(
    "",
    response_model=EventAdminDetail,
    status_code=status.HTTP_201_CREATED,
    summary="创建活动（草稿）",
)
async def create_event(
    payload: EventCreate, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> EventAdminDetail:
    return await event_service.create_event(session, user, payload, ip=ip)


@router.get("/{event_id}", response_model=EventAdminDetail, summary="活动详情（管理端）")
async def get_event(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession
) -> EventAdminDetail:
    return await event_service.get_event_detail(session, event_id, user)


@router.patch("/{event_id}", response_model=EventAdminDetail, summary="编辑活动")
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    user: OrganizerUser,
    session: DbSession,
    ip: ClientIp,
) -> EventAdminDetail:
    return await event_service.update_event(session, user, event_id, payload, ip=ip)


@router.post("/{event_id}/publish", response_model=PublishResponse, summary="发布活动")
async def publish_event(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> PublishResponse:
    event = await event_service.publish_event(session, user, event_id, ip=ip)
    return PublishResponse(id=event.id, status=event.status, published_at=event.published_at)


@router.post("/{event_id}/cancel", response_model=MessageResponse, summary="取消活动")
async def cancel_event(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> MessageResponse:
    await event_service.cancel_event(session, user, event_id, ip=ip)
    return MessageResponse(message="活动已取消")


@router.post(
    "/{event_id}/static-code/rotate",
    response_model=StaticCodeRotateResponse,
    summary="轮换静态口令（明文仅返回一次）",
)
async def rotate_static_code(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> StaticCodeRotateResponse:
    return await event_service.rotate_static_code(session, user, event_id, ip=ip)


@router.get(
    "/{event_id}/qr",
    response_model=QrChallengeOut,
    summary="获取当前动态二维码（过期自动刷新）",
)
async def current_qr(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession
) -> QrChallengeOut:
    return await event_service.current_qr(session, user, event_id)


@router.post(
    "/{event_id}/qr/rotate",
    response_model=QrChallengeOut,
    summary="强制刷新动态二维码",
)
async def rotate_qr(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession
) -> QrChallengeOut:
    return await event_service.current_qr(session, user, event_id, force=True)
