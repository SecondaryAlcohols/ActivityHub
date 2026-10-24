"""管理端控制台、名单、异常、统计与导出。"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Conflict, NotFound
from app.core.pagination import Page, PageParams
from app.models.anomaly import Anomaly
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    AnomalyStatus,
    AnomalyType,
    AttendanceKind,
    AttendanceStatus,
    AuditAction,
    EventStatus,
    RegistrationStatus,
)
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.schemas.admin import (
    AnomalyItem,
    AuditLogItem,
    ConsoleAnomalyItem,
    ConsoleRecentItem,
    ConsoleResponse,
    EventStatItem,
    ResolveAnomalyRequest,
    RosterItem,
    RosterState,
    StatsOverview,
)
from app.services import audit
from app.services.admin_events import (
    count_event,
    current_qr,
    load_event_for_admin,
)
from app.services.event_common import mask_phone, verified_methods
from app.utils.time import utcnow


async def get_console(
    session: AsyncSession, actor: User, event_id: uuid.UUID
) -> ConsoleResponse:
    event = await load_event_for_admin(session, actor, event_id)
    counts = await count_event(session, event.id)

    rows = (
        await session.execute(
            select(AttendanceRecord, User)
            .join(User, AttendanceRecord.user_id == User.id)
            .where(AttendanceRecord.event_id == event.id)
            .order_by(AttendanceRecord.occurred_at.desc())
            .limit(10)
        )
    ).all()

    record_ids = [record.id for record, _ in rows]
    anomaly_map = await _anomalies_by_record(session, record_ids)

    recent = [
        ConsoleRecentItem(
            record_id=record.id,
            user_name=user.name,
            student_no=user.student_no,
            kind=record.kind,
            occurred_at=record.occurred_at,
            distance_m=record.distance_m,
            ip=record.ip,
            face_similarity=record.face_similarity,
            is_manual=record.is_manual,
            status=record.status,
            anomaly_types=anomaly_map.get(record.id, []),
        )
        for record, user in rows
    ]

    anomaly_rows = (
        await session.execute(
            select(Anomaly, User)
            .outerjoin(User, Anomaly.user_id == User.id)
            .where(Anomaly.event_id == event.id, Anomaly.status == AnomalyStatus.OPEN)
            .order_by(Anomaly.detected_at.desc())
            .limit(5)
        )
    ).all()
    anomalies = [
        ConsoleAnomalyItem(
            id=anomaly.id,
            type=anomaly.type,
            user_name=user.name if user else None,
            student_no=user.student_no if user else None,
            detail=anomaly.detail,
            detected_at=anomaly.detected_at,
        )
        for anomaly, user in anomaly_rows
    ]

    qr = await current_qr(session, actor, event.id) if event.require_qr else None

    return ConsoleResponse(
        event_id=event.id,
        title=event.title,
        counts=counts,
        recent=recent,
        anomalies=anomalies,
        qr=qr,
        server_time=utcnow(),
    )


async def list_roster(
    session: AsyncSession,
    actor: User,
    event_id: uuid.UUID,
    *,
    state: RosterState,
    q: str | None,
    params: PageParams,
) -> Page[RosterItem]:
    event = await load_event_for_admin(session, actor, event_id)

    checkin_exists = (
        select(AttendanceRecord.id)
        .where(
            AttendanceRecord.registration_id == Registration.id,
            AttendanceRecord.kind == AttendanceKind.CHECKIN,
        )
        .exists()
    )
    checkout_exists = (
        select(AttendanceRecord.id)
        .where(
            AttendanceRecord.registration_id == Registration.id,
            AttendanceRecord.kind == AttendanceKind.CHECKOUT,
        )
        .exists()
    )
    flagged_exists = (
        select(AttendanceRecord.id)
        .where(
            AttendanceRecord.registration_id == Registration.id,
            AttendanceRecord.status == AttendanceStatus.FLAGGED,
        )
        .exists()
    )

    conditions = [
        Registration.event_id == event.id,
        Registration.status.in_((RegistrationStatus.PENDING, RegistrationStatus.APPROVED)),
    ]
    if state == RosterState.PENDING:
        conditions.append(Registration.status == RegistrationStatus.PENDING)
    elif state == RosterState.ABSENT:
        conditions.extend([Registration.status == RegistrationStatus.APPROVED, ~checkin_exists])
    elif state == RosterState.CHECKED_IN:
        conditions.extend([checkin_exists, ~checkout_exists])
    elif state == RosterState.CHECKED_OUT:
        conditions.append(checkout_exists)
    elif state == RosterState.FLAGGED:
        conditions.append(flagged_exists)

    if q:
        keyword = f"%{q.strip()}%"
        ip_exists = (
            select(AttendanceRecord.id)
            .where(
                AttendanceRecord.registration_id == Registration.id,
                AttendanceRecord.ip.ilike(keyword),
            )
            .exists()
        )
        conditions.append(
            or_(
                User.name.ilike(keyword),
                User.student_no.ilike(keyword),
                User.phone.ilike(keyword),
                ip_exists,
            )
        )

    total = await session.scalar(
        select(func.count(Registration.id))
        .select_from(Registration)
        .join(User, Registration.user_id == User.id)
        .where(*conditions)
    )
    rows = (
        await session.execute(
            select(Registration, User)
            .join(User, Registration.user_id == User.id)
            .where(*conditions)
            .order_by(Registration.applied_at.desc())
            .offset(params.offset)
            .limit(params.size)
        )
    ).all()

    registration_ids = [registration.id for registration, _ in rows]
    user_ids = [user.id for _, user in rows]
    records = (
        await session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.registration_id.in_(registration_ids)
            )
        )
    ).all() if registration_ids else []
    by_registration: dict[uuid.UUID, dict[AttendanceKind, AttendanceRecord]] = defaultdict(dict)
    for record in records:
        by_registration[record.registration_id][record.kind] = record

    anomaly_map = await _open_anomaly_map(session, event.id, user_ids)

    items = []
    for registration, user in rows:
        kinds = by_registration.get(registration.id, {})
        checkin = kinds.get(AttendanceKind.CHECKIN)
        checkout = kinds.get(AttendanceKind.CHECKOUT)
        item_anomalies = anomaly_map.get(user.id, [])
        flagged = bool(
            (checkin and checkin.status == AttendanceStatus.FLAGGED)
            or (checkout and checkout.status == AttendanceStatus.FLAGGED)
            or item_anomalies
        )
        items.append(
            RosterItem(
                registration_id=registration.id,
                user_id=user.id,
                student_no=user.student_no,
                name=user.name,
                college=user.college,
                phone_masked=mask_phone(user.phone),
                status=registration.status,
                applied_at=registration.applied_at,
                checkin_at=checkin.occurred_at if checkin else None,
                checkout_at=checkout.occurred_at if checkout else None,
                checkin_methods=verified_methods(checkin.verified_methods) if checkin else [],
                checkout_methods=verified_methods(checkout.verified_methods) if checkout else [],
                distance_m=checkin.distance_m if checkin else None,
                ip=checkin.ip if checkin else None,
                face_similarity=checkin.face_similarity if checkin else None,
                is_manual=bool((checkin and checkin.is_manual) or (checkout and checkout.is_manual)),
                flagged=flagged,
                anomaly_types=item_anomalies,
                can_manual_checkin=(
                    registration.status == RegistrationStatus.APPROVED and checkin is None
                ),
            )
        )
    return Page.build(items, int(total or 0), params)


async def list_anomalies(
    session: AsyncSession,
    actor: User,
    event_id: uuid.UUID,
    *,
    status: AnomalyStatus | None,
    params: PageParams,
) -> Page[AnomalyItem]:
    event = await load_event_for_admin(session, actor, event_id)
    conditions = [Anomaly.event_id == event.id]
    if status:
        conditions.append(Anomaly.status == status)

    total = await session.scalar(select(func.count(Anomaly.id)).where(*conditions))
    rows = (
        await session.execute(
            select(Anomaly, User)
            .outerjoin(User, Anomaly.user_id == User.id)
            .where(*conditions)
            .order_by(Anomaly.detected_at.desc())
            .offset(params.offset)
            .limit(params.size)
        )
    ).all()

    items = [
        AnomalyItem(
            id=anomaly.id,
            type=anomaly.type,
            status=anomaly.status,
            user_id=anomaly.user_id,
            user_name=user.name if user else None,
            student_no=user.student_no if user else None,
            detail=anomaly.detail,
            detected_at=anomaly.detected_at,
            resolved_at=anomaly.resolved_at,
            resolution_note=anomaly.resolution_note,
        )
        for anomaly, user in rows
    ]
    return Page.build(items, int(total or 0), params)


async def resolve_anomaly(
    session: AsyncSession,
    actor: User,
    anomaly_id: uuid.UUID,
    payload: ResolveAnomalyRequest,
    *,
    ip: str | None,
) -> Anomaly:
    anomaly = await session.get(Anomaly, anomaly_id)
    if anomaly is None:
        raise NotFound("异常记录不存在", code="anomaly_not_found")
    await load_event_for_admin(session, actor, anomaly.event_id)

    if anomaly.status != AnomalyStatus.OPEN:
        raise Conflict("该异常已处理", code="anomaly_already_resolved")

    anomaly.status = AnomalyStatus.DISMISSED if payload.dismiss else AnomalyStatus.RESOLVED
    anomaly.resolved_at = utcnow()
    anomaly.resolved_by = actor.id
    anomaly.resolution_note = payload.resolution_note
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.ANOMALY_RESOLVED,
        target_type="anomaly",
        target_id=anomaly.id,
        payload={"dismiss": payload.dismiss, "note": payload.resolution_note},
        ip=ip,
    )
    await session.commit()
    return anomaly


async def stats_overview(session: AsyncSession, actor: User, days: int) -> StatsOverview:
    now = utcnow()
    since = now - timedelta(days=days)

    conditions = [
        Event.status == EventStatus.PUBLISHED,
        Event.start_at >= since,
        Event.start_at <= now,
    ]
    if actor.role.value == "organizer":
        from app.models.user import Organization

        conditions.append(
            or_(
                Event.created_by == actor.id,
                Event.id.in_(
                    select(Event.id)
                    .join(Organization, Event.org_id == Organization.id)
                    .where(Organization.owner_id == actor.id)
                ),
            )
        )

    rows = (
        await session.execute(
            select(Event.id, Event.title, Event.start_at).where(*conditions).order_by(Event.start_at.desc())
        )
    ).all()

    items: list[EventStatItem] = []
    registration_total = 0
    checkin_total = 0
    for event_id, title, start_at in rows:
        approved = await session.scalar(
            select(func.count(Registration.id)).where(
                Registration.event_id == event_id,
                Registration.status == RegistrationStatus.APPROVED,
            )
        )
        checked_in = await session.scalar(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.event_id == event_id,
                AttendanceRecord.kind == AttendanceKind.CHECKIN,
            )
        )
        approved_count = int(approved or 0)
        checkin_count = int(checked_in or 0)
        registration_total += approved_count
        checkin_total += checkin_count
        items.append(
            EventStatItem(
                event_id=event_id,
                title=title,
                start_at=start_at,
                approved=approved_count,
                checked_in=checkin_count,
                checkin_rate=round(checkin_count / approved_count, 4) if approved_count else 0.0,
            )
        )

    return StatsOverview(
        days=days,
        event_count=len(items),
        registration_total=registration_total,
        checkin_total=checkin_total,
        overall_checkin_rate=(
            round(checkin_total / registration_total, 4) if registration_total else 0.0
        ),
        events=items,
    )


async def export_csv(
    session: AsyncSession,
    actor: User,
    event_id: uuid.UUID,
    *,
    ip: str | None,
) -> tuple[str, str]:
    event = await load_event_for_admin(session, actor, event_id)
    rows = (
        await session.execute(
            select(Registration, User)
            .join(User, Registration.user_id == User.id)
            .where(Registration.event_id == event.id)
            .order_by(Registration.applied_at.asc())
        )
    ).all()

    registration_ids = [registration.id for registration, _ in rows]
    user_ids = [user.id for _, user in rows]
    records = (
        await session.scalars(
            select(AttendanceRecord).where(AttendanceRecord.registration_id.in_(registration_ids))
        )
    ).all() if registration_ids else []
    by_registration: dict[uuid.UUID, dict[AttendanceKind, AttendanceRecord]] = defaultdict(dict)
    for record in records:
        by_registration[record.registration_id][record.kind] = record

    anomaly_map = await _open_anomaly_map(session, event.id, user_ids)
    method_labels = {
        "qr": "动态二维码",
        "static_code": "静态口令",
        "gps": "GPS",
        "ip": "IP",
        "face": "人脸",
        "manual": "人工补签",
    }

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "学号", "姓名", "学院", "手机号", "报名状态", "报名时间",
            "签到时间", "签退时间", "签到方式", "签退方式",
            "签到距离(米)", "签到IP", "人脸相似度", "考勤时长(分钟)", "异常",
        ]
    )
    for registration, user in rows:
        kinds = by_registration.get(registration.id, {})
        checkin = kinds.get(AttendanceKind.CHECKIN)
        checkout = kinds.get(AttendanceKind.CHECKOUT)
        duration = None
        if checkin and checkout:
            duration = int((checkout.occurred_at - checkin.occurred_at).total_seconds() // 60)
        writer.writerow(
            [
                user.student_no,
                user.name,
                user.college or "",
                user.phone or "",
                _registration_label(registration.status),
                registration.applied_at.isoformat(),
                checkin.occurred_at.isoformat() if checkin else "",
                checkout.occurred_at.isoformat() if checkout else "",
                "、".join(method_labels.get(m, m) for m in (checkin.verified_methods if checkin else [])),
                "、".join(method_labels.get(m, m) for m in (checkout.verified_methods if checkout else [])),
                f"{checkin.distance_m:.0f}" if checkin and checkin.distance_m is not None else "",
                checkin.ip if checkin else "",
                f"{checkin.face_similarity:.2f}" if checkin and checkin.face_similarity is not None else "",
                duration if duration is not None else "",
                "、".join(_anomaly_label(t) for t in anomaly_map.get(user.id, [])),
            ]
        )

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.EXPORT_DOWNLOADED,
        target_type="event",
        target_id=event.id,
        payload={"rows": len(rows)},
        ip=ip,
    )
    await session.commit()
    filename = f"{event.title}-考勤明细.csv".replace("/", "_").replace("\\", "_")
    return buffer.getvalue(), filename


async def _anomalies_by_record(
    session: AsyncSession, record_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[AnomalyType]]:
    if not record_ids:
        return {}
    rows = (
        await session.execute(
            select(Anomaly.attendance_record_id, Anomaly.type).where(
                Anomaly.attendance_record_id.in_(record_ids),
                Anomaly.status == AnomalyStatus.OPEN,
            )
        )
    ).all()
    result: dict[uuid.UUID, list[AnomalyType]] = defaultdict(list)
    for record_id, anomaly_type in rows:
        result[record_id].append(anomaly_type)
    return result


async def _open_anomaly_map(
    session: AsyncSession, event_id: uuid.UUID, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[AnomalyType]]:
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(Anomaly.user_id, Anomaly.type).where(
                Anomaly.event_id == event_id,
                Anomaly.user_id.in_(user_ids),
                Anomaly.status == AnomalyStatus.OPEN,
            )
        )
    ).all()
    result: dict[uuid.UUID, list[AnomalyType]] = defaultdict(list)
    for user_id, anomaly_type in rows:
        if user_id is not None and anomaly_type not in result[user_id]:
            result[user_id].append(anomaly_type)
    return result


def _registration_label(status: RegistrationStatus) -> str:
    return {
        RegistrationStatus.PENDING: "待审核",
        RegistrationStatus.APPROVED: "已通过",
        RegistrationStatus.REJECTED: "已拒绝",
        RegistrationStatus.CANCELLED: "已取消",
    }[status]


def _anomaly_label(anomaly_type: AnomalyType) -> str:
    return {
        AnomalyType.SAME_IP: "同 IP 多账号",
        AnomalyType.FAILED_ATTEMPTS: "连续校验失败",
        AnomalyType.MANUAL_OVERRIDE: "人工补签",
    }[anomaly_type]


async def list_audit_logs(
    session: AsyncSession,
    *,
    action: str | None,
    target_id: str | None,
    params: PageParams,
) -> Page[AuditLogItem]:
    from app.models.audit import AuditLog

    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if target_id:
        conditions.append(AuditLog.target_id == target_id)

    total = await session.scalar(
        select(func.count(AuditLog.id)).where(*conditions)
    )
    rows = (
        await session.execute(
            select(AuditLog, User)
            .outerjoin(User, AuditLog.actor_id == User.id)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc())
            .offset(params.offset)
            .limit(params.size)
        )
    ).all()

    items = [
        AuditLogItem(
            id=log.id,
            actor_name=actor.name if actor else None,
            actor_role=log.actor_role,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            payload=log.payload,
            created_at=log.created_at,
        )
        for log, actor in rows
    ]
    return Page.build(items, int(total or 0), params)
