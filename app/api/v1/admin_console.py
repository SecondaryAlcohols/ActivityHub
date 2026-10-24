"""管理端控制台、名单、审核、异常、统计与导出接口。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AdminUser,
    ClientIp,
    DbSession,
    OrganizerUser,
    PageQuery,
    UserSnapshot,
)
from app.core.exceptions import NotFound
from app.core.pagination import Page
from app.db.session import SessionFactory
from app.models.enums import AnomalyStatus
from app.models.registration import Registration
from app.models.user import User
from app.schemas.admin import (
    AnomalyItem,
    ApproveResponse,
    AuditLogItem,
    ConsoleResponse,
    ManualCheckinRequest,
    RejectRequest,
    ResolveAnomalyRequest,
    RosterItem,
    RosterState,
    StatsOverview,
)
from app.schemas.attendance import AttendanceRecordOut
from app.schemas.common import MessageResponse
from app.services import attendance as attendance_service
from app.services import console as console_service
from app.services import registrations as registration_service
from app.services.admin_events import load_event_for_admin

logger = logging.getLogger("activityhub.stream")

router = APIRouter(prefix="/admin", tags=["管理端 · 考勤与统计"])


@router.get(
    "/events/{event_id}/console",
    response_model=ConsoleResponse,
    summary="签到控制台快照",
)
async def console(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession
) -> ConsoleResponse:
    return await console_service.get_console(session, user, event_id)


@router.get("/events/{event_id}/console/stream", summary="签到控制台实时流（SSE）")
async def console_stream(
    event_id: uuid.UUID, request: Request, user: UserSnapshot
) -> StreamingResponse:
    user_id = user.id

    async def generate():
        fingerprint: str | None = None
        last_heartbeat = 0.0
        while True:
            if await request.is_disconnected():
                return
            try:
                async with SessionFactory() as session:
                    actor = await session.get(User, user_id)
                    if actor is None:
                        return
                    snapshot = await console_service.get_console(session, actor, event_id)
                payload = snapshot.model_dump(mode="json")
                current = hashlib.sha256(
                    json.dumps(
                        [payload["counts"], payload["recent"], payload["anomalies"], payload["qr"]],
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                if current != fingerprint:
                    fingerprint = current
                    last_heartbeat = time.monotonic()
                    yield f"event: snapshot\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                elif time.monotonic() - last_heartbeat > 15:
                    last_heartbeat = time.monotonic()
                    yield ": keep-alive\n\n"
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("控制台实时流异常 event_id=%s", event_id)
                yield 'event: error\ndata: {"message":"实时流异常，请刷新重试"}\n\n'
                return
            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/events/{event_id}/roster",
    response_model=Page[RosterItem],
    summary="报名/签到名单",
)
async def roster(
    event_id: uuid.UUID,
    user: OrganizerUser,
    session: DbSession,
    params: PageQuery,
    state: RosterState = Query(RosterState.ALL, description="筛选状态"),
    q: str | None = Query(None, max_length=60, description="姓名/学号/手机号/IP"),
) -> Page[RosterItem]:
    return await console_service.list_roster(
        session, user, event_id, state=state, q=q, params=params
    )


@router.get(
    "/events/{event_id}/anomalies",
    response_model=Page[AnomalyItem],
    summary="考勤异常列表",
)
async def anomalies(
    event_id: uuid.UUID,
    user: OrganizerUser,
    session: DbSession,
    params: PageQuery,
    status: AnomalyStatus | None = Query(None),
) -> Page[AnomalyItem]:
    return await console_service.list_anomalies(
        session, user, event_id, status=status, params=params
    )


@router.post(
    "/anomalies/{anomaly_id}/resolve",
    response_model=MessageResponse,
    summary="处理异常",
)
async def resolve_anomaly(
    anomaly_id: uuid.UUID,
    payload: ResolveAnomalyRequest,
    user: OrganizerUser,
    session: DbSession,
    ip: ClientIp,
) -> MessageResponse:
    await console_service.resolve_anomaly(session, user, anomaly_id, payload, ip=ip)
    return MessageResponse(message="异常已处理")


@router.get(
    "/events/{event_id}/export.csv",
    summary="导出考勤明细（CSV，Excel 可直接打开）",
    response_class=Response,
)
async def export_csv(
    event_id: uuid.UUID, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> Response:
    content, filename = await console_service.export_csv(session, user, event_id, ip=ip)
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )


@router.get("/stats/overview", response_model=StatsOverview, summary="签到率概览")
async def stats_overview(
    user: OrganizerUser,
    session: DbSession,
    days: int = Query(7, ge=1, le=90, description="统计最近天数"),
) -> StatsOverview:
    return await console_service.stats_overview(session, user, days)


# --------------------------------------------------------------------------- #
# 报名审核与人工补签
# --------------------------------------------------------------------------- #
async def _registration_for_admin(session, actor: User, registration_id: uuid.UUID) -> Registration:
    registration = await session.get(Registration, registration_id)
    if registration is None:
        raise NotFound("报名记录不存在", code="registration_not_found")
    await load_event_for_admin(session, actor, registration.event_id)
    return registration


@router.post(
    "/registrations/{registration_id}/approve",
    response_model=ApproveResponse,
    summary="审核通过",
)
async def approve_registration(
    registration_id: uuid.UUID, user: OrganizerUser, session: DbSession, ip: ClientIp
) -> ApproveResponse:
    await _registration_for_admin(session, user, registration_id)
    registration = await registration_service.approve(session, user, registration_id, ip)
    return ApproveResponse(registration_id=registration.id, status=registration.status)


@router.post(
    "/registrations/{registration_id}/reject",
    response_model=ApproveResponse,
    summary="审核拒绝",
)
async def reject_registration(
    registration_id: uuid.UUID,
    payload: RejectRequest,
    user: OrganizerUser,
    session: DbSession,
    ip: ClientIp,
) -> ApproveResponse:
    await _registration_for_admin(session, user, registration_id)
    registration = await registration_service.reject(
        session, user, registration_id, payload.reason, ip
    )
    return ApproveResponse(registration_id=registration.id, status=registration.status)


@router.post(
    "/registrations/{registration_id}/manual-checkin",
    response_model=AttendanceRecordOut,
    summary="人工补签（写入审计日志）",
)
async def manual_checkin(
    registration_id: uuid.UUID,
    payload: ManualCheckinRequest,
    user: OrganizerUser,
    session: DbSession,
    ip: ClientIp,
) -> AttendanceRecordOut:
    await _registration_for_admin(session, user, registration_id)
    record = await attendance_service.manual_checkin(
        session, user, registration_id, payload, ip=ip
    )
    return attendance_service.to_record_out(record)


@router.get(
    "/audit-logs",
    response_model=Page[AuditLogItem],
    summary="审计日志（仅管理员）",
)
async def audit_logs(
    user: AdminUser,
    session: DbSession,
    params: PageQuery,
    action: str | None = Query(None, max_length=64),
    target_id: str | None = Query(None, max_length=36),
) -> Page[AuditLogItem]:
    return await console_service.list_audit_logs(
        session, action=action, target_id=target_id, params=params
    )
