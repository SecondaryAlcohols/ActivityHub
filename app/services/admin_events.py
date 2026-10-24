"""管理端活动管理：创建、编辑、发布、二维码签发。"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import Conflict, Forbidden, NotFound
from app.core.pagination import Page, PageParams
from app.core.security import build_qr_token, derive_display_code, generate_numeric_code, hash_secret
from app.models.anomaly import Anomaly
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    AnomalyStatus,
    AttendanceKind,
    AuditAction,
    EventStatus,
    RegistrationStatus,
    UserRole,
)
from app.models.event import Event
from app.models.qr import QrChallenge
from app.models.registration import Registration
from app.models.user import Organization, User
from app.schemas.admin import QrChallengeOut
from app.schemas.event import (
    EventAdminDetail,
    EventAdminItem,
    EventCounts,
    EventCreate,
    EventUpdate,
    StaticCodeRotateResponse,
)
from app.services import audit
from app.services.event_common import (
    ACTIVE_REGISTRATION_STATUSES,
    build_policy,
    compute_phase,
    methods_of,
)
from app.utils.time import seconds_until, utcnow

QR_TTL_GRACE_SECONDS = 2


async def create_event(
    session: AsyncSession, actor: User, payload: EventCreate, *, ip: str | None
) -> EventAdminDetail:
    org = await _resolve_organization(session, actor, payload.org_id)

    event = Event(
        org_id=org.id,
        created_by=actor.id,
        title=payload.title,
        description=payload.description,
        location_name=payload.location_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        cover_color=payload.cover_color,
        start_at=payload.start_at,
        end_at=payload.end_at,
        registration_deadline=payload.registration_deadline,
        capacity=payload.capacity,
        requires_approval=payload.requires_approval,
        status=EventStatus.DRAFT,
        checkin_mode=payload.checkin_mode,
        checkin_opens_minutes_before=payload.checkin_opens_minutes_before,
        checkin_closes_minutes_after=payload.checkin_closes_minutes_after,
        checkout_deadline_minutes=payload.checkout_deadline_minutes,
        require_qr=payload.require_qr,
        qr_rotation_seconds=payload.qr_rotation_seconds,
        require_static_code=payload.require_static_code,
        static_code_valid_from=payload.static_code_valid_from,
        static_code_valid_to=payload.static_code_valid_to,
        require_gps=payload.require_gps,
        gps_radius_m=payload.gps_radius_m,
        gps_max_accuracy_m=payload.gps_max_accuracy_m,
        require_ip=payload.require_ip,
        allowed_ip_cidrs=payload.allowed_ip_cidrs,
        require_face=payload.require_face,
        face_match_threshold=payload.face_match_threshold,
    )
    if payload.require_static_code and payload.static_code:
        event.static_code_hash = await asyncio.to_thread(hash_secret, payload.static_code)

    session.add(event)
    await session.flush()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.EVENT_CREATED,
        target_type="event",
        target_id=event.id,
        payload={"title": event.title},
        ip=ip,
    )
    await session.commit()
    return await get_event_detail(session, event.id, actor)


async def update_event(
    session: AsyncSession,
    actor: User,
    event_id: uuid.UUID,
    payload: EventUpdate,
    *,
    ip: str | None,
) -> EventAdminDetail:
    event = await load_event_for_admin(session, actor, event_id)
    if event.status == EventStatus.CANCELLED:
        raise Conflict("已取消的活动不可编辑", code="event_cancelled")

    changes = payload.model_dump(exclude_unset=True)
    static_code = changes.pop("static_code", None)

    for field, value in changes.items():
        setattr(event, field, value)

    if static_code:
        event.static_code_hash = await asyncio.to_thread(hash_secret, static_code)
        if not event.require_static_code:
            event.require_static_code = True

    if event.require_static_code and static_code is None and not event.static_code_hash:
        raise Conflict("启用静态口令时必须设置 6 位口令", code="static_code_required")
    if not event.require_static_code:
        event.static_code_hash = None
        event.static_code_valid_from = None
        event.static_code_valid_to = None

    await _validate_event_times(event)
    await _ensure_capacity(session, event)

    if event.status == EventStatus.PUBLISHED:
        _validate_publishable(event)

    await audit.record(
        session,
        actor=actor,
        action=AuditAction.EVENT_UPDATED,
        target_type="event",
        target_id=event.id,
        payload={"fields": sorted(changes.keys())},
        ip=ip,
    )
    await session.commit()
    return await get_event_detail(session, event.id, actor)


async def publish_event(
    session: AsyncSession, actor: User, event_id: uuid.UUID, *, ip: str | None
) -> Event:
    event = await load_event_for_admin(session, actor, event_id)
    if event.status == EventStatus.PUBLISHED:
        raise Conflict("活动已发布", code="event_already_published")
    if event.status == EventStatus.CANCELLED:
        raise Conflict("已取消的活动不可发布", code="event_cancelled")
    if event.end_at <= utcnow():
        raise Conflict("活动结束时间已过，无法发布", code="event_ended")

    _validate_publishable(event)
    event.status = EventStatus.PUBLISHED
    event.published_at = utcnow()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.EVENT_PUBLISHED,
        target_type="event",
        target_id=event.id,
        ip=ip,
    )
    await session.commit()
    return event


async def cancel_event(
    session: AsyncSession, actor: User, event_id: uuid.UUID, *, ip: str | None
) -> Event:
    event = await load_event_for_admin(session, actor, event_id)
    if event.status == EventStatus.CANCELLED:
        raise Conflict("活动已取消", code="event_cancelled")
    event.status = EventStatus.CANCELLED
    event.cancelled_at = utcnow()
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.EVENT_CANCELLED,
        target_type="event",
        target_id=event.id,
        ip=ip,
    )
    await session.commit()
    return event


async def list_events(
    session: AsyncSession,
    actor: User,
    *,
    q: str | None,
    status: EventStatus | None,
    params: PageParams,
) -> Page[EventAdminItem]:
    conditions = _access_conditions(actor)
    if status:
        conditions.append(Event.status == status)
    if q:
        keyword = f"%{q.strip()}%"
        conditions.append(
            or_(Event.title.ilike(keyword), Event.location_name.ilike(keyword))
        )

    base = select(Event, Organization).join(Organization, Event.org_id == Organization.id).where(*conditions)
    total = await session.scalar(
        select(func.count(Event.id))
        .select_from(Event)
        .join(Organization, Event.org_id == Organization.id)
        .where(*conditions)
    )
    rows = (
        await session.execute(
            base.order_by(Event.start_at.desc()).offset(params.offset).limit(params.size)
        )
    ).all()

    event_ids = [row[0].id for row in rows]
    stats = await _registration_stats(session, event_ids)
    now = utcnow()
    items = [
        EventAdminItem(
            id=event.id,
            title=event.title,
            org_name=org.name,
            location_name=event.location_name,
            cover_color=event.cover_color,
            start_at=event.start_at,
            end_at=event.end_at,
            status=event.status,
            phase=compute_phase(event, now),
            capacity=event.capacity,
            approved_count=stats.get(event.id, {}).get(RegistrationStatus.APPROVED, 0),
            pending_count=stats.get(event.id, {}).get(RegistrationStatus.PENDING, 0),
            methods=methods_of(event),
            checkin_mode=event.checkin_mode,
        )
        for event, org in rows
    ]
    return Page.build(items, int(total or 0), params)


async def get_event_detail(
    session: AsyncSession, event_id: uuid.UUID, actor: User
) -> EventAdminDetail:
    event = await load_event_for_admin(session, actor, event_id)
    counts = await count_event(session, event.id)
    now = utcnow()
    return EventAdminDetail(
        id=event.id,
        title=event.title,
        org_name=event.org.name,
        location_name=event.location_name,
        cover_color=event.cover_color,
        start_at=event.start_at,
        end_at=event.end_at,
        status=event.status,
        phase=compute_phase(event, now),
        capacity=event.capacity,
        approved_count=counts.approved,
        pending_count=counts.pending,
        methods=methods_of(event),
        checkin_mode=event.checkin_mode,
        description=event.description,
        latitude=event.latitude,
        longitude=event.longitude,
        registration_deadline=event.registration_deadline,
        requires_approval=event.requires_approval,
        policy=build_policy(event),
        static_code_set=event.static_code_hash is not None,
        counts=counts,
    )


async def rotate_static_code(
    session: AsyncSession, actor: User, event_id: uuid.UUID, *, ip: str | None
) -> StaticCodeRotateResponse:
    event = await load_event_for_admin(session, actor, event_id)
    if not event.require_static_code:
        raise Conflict("该活动未启用静态口令", code="static_code_disabled")

    code = generate_numeric_code(6)
    event.static_code_hash = await asyncio.to_thread(hash_secret, code)
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.STATIC_CODE_ROTATED,
        target_type="event",
        target_id=event.id,
        ip=ip,
    )
    await session.commit()
    return StaticCodeRotateResponse(
        static_code=code,
        valid_from=event.static_code_valid_from,
        valid_to=event.static_code_valid_to,
    )


async def current_qr(
    session: AsyncSession,
    actor: User,
    event_id: uuid.UUID,
    *,
    force: bool = False,
) -> QrChallengeOut:
    event = await load_event_for_admin(session, actor, event_id)
    if not event.require_qr:
        raise Conflict("该活动未启用动态二维码", code="qr_disabled")

    now = utcnow()
    if not force:
        existing = await session.scalar(
            select(QrChallenge)
            .where(QrChallenge.event_id == event.id, QrChallenge.expires_at > now)
            .order_by(QrChallenge.issued_at.desc())
            .limit(1)
        )
        if existing is not None:
            return _qr_out(existing, event.qr_rotation_seconds, now)

    issued_at = now
    expires_at = issued_at + timedelta(seconds=event.qr_rotation_seconds + QR_TTL_GRACE_SECONDS)
    nonce = secrets.token_hex(8)
    challenge = QrChallenge(
        event_id=event.id,
        nonce=nonce,
        code=derive_display_code(nonce),
        issued_by=actor.id,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    session.add(challenge)
    await session.commit()
    return _qr_out(challenge, event.qr_rotation_seconds, now)


async def load_event_for_admin(session: AsyncSession, actor: User, event_id: uuid.UUID) -> Event:
    event = await session.scalar(
        select(Event).options(joinedload(Event.org)).where(Event.id == event_id)
    )
    if event is None:
        raise NotFound("活动不存在", code="event_not_found")
    if actor.role == UserRole.ADMIN:
        return event
    if actor.role != UserRole.ORGANIZER:
        raise Forbidden("需要组织者或管理员权限")
    if event.created_by == actor.id or (event.org and event.org.owner_id == actor.id):
        return event
    raise Forbidden("只能管理自己发布的活动")


async def count_event(session: AsyncSession, event_id: uuid.UUID) -> EventCounts:
    reg_rows = (
        await session.execute(
            select(Registration.status, func.count(Registration.id))
            .where(Registration.event_id == event_id)
            .group_by(Registration.status)
        )
    ).all()
    reg_counts = {status: int(count) for status, count in reg_rows}

    att_rows = (
        await session.execute(
            select(AttendanceRecord.kind, func.count(AttendanceRecord.id))
            .where(AttendanceRecord.event_id == event_id)
            .group_by(AttendanceRecord.kind)
        )
    ).all()
    att_counts = {kind: int(count) for kind, count in att_rows}

    anomaly_open = await session.scalar(
        select(func.count(Anomaly.id)).where(
            Anomaly.event_id == event_id, Anomaly.status == AnomalyStatus.OPEN
        )
    )

    approved = reg_counts.get(RegistrationStatus.APPROVED, 0)
    checked_in = att_counts.get(AttendanceKind.CHECKIN, 0)
    checked_out = att_counts.get(AttendanceKind.CHECKOUT, 0)
    return EventCounts(
        approved=approved,
        pending=reg_counts.get(RegistrationStatus.PENDING, 0),
        checked_in=checked_in,
        checked_out=checked_out,
        absent=max(0, approved - checked_in),
        anomaly_open=int(anomaly_open or 0),
        checkin_rate=round(checked_in / approved, 4) if approved else 0.0,
    )


# --------------------------------------------------------------------------- #
# 内部工具
# --------------------------------------------------------------------------- #
def _qr_out(challenge: QrChallenge, rotation: int, now) -> QrChallengeOut:
    return QrChallengeOut(
        token=build_qr_token(challenge.nonce, str(challenge.event_id), challenge.expires_at),
        code=challenge.code,
        issued_at=challenge.issued_at,
        expires_at=challenge.expires_at,
        expires_in=seconds_until(challenge.expires_at, now=now),
        rotation_seconds=rotation,
    )


def _access_conditions(actor: User) -> list:
    if actor.role == UserRole.ADMIN:
        return []
    if actor.role != UserRole.ORGANIZER:
        raise Forbidden("需要组织者或管理员权限")
    return [or_(Event.created_by == actor.id, Organization.owner_id == actor.id)]


async def _resolve_organization(
    session: AsyncSession, actor: User, org_id: uuid.UUID | None
) -> Organization:
    if org_id is not None:
        org = await session.get(Organization, org_id)
        if org is None:
            raise NotFound("主办方不存在", code="organization_not_found")
        if actor.role != UserRole.ADMIN and org.owner_id != actor.id:
            raise Forbidden("只能为本单位创建活动")
        return org

    org = await session.scalar(
        select(Organization).where(Organization.owner_id == actor.id).order_by(Organization.created_at).limit(1)
    )
    if org is None:
        raise Conflict("当前账号未绑定主办方，请联系管理员", code="organization_missing")
    return org


async def _validate_event_times(event: Event) -> None:
    if event.end_at <= event.start_at:
        raise Conflict("结束时间必须晚于开始时间", code="invalid_time_range")
    if event.registration_deadline > event.start_at:
        raise Conflict("报名截止时间不能晚于活动开始时间", code="invalid_registration_deadline")
    if event.require_gps and (event.latitude is None or event.longitude is None):
        raise Conflict("启用 GPS 考勤时必须设置活动经纬度", code="location_missing")
    if event.require_static_code and not event.static_code_hash:
        raise Conflict("启用静态口令时必须设置 6 位口令", code="static_code_required")
    if (
        event.static_code_valid_from
        and event.static_code_valid_to
        and event.static_code_valid_to <= event.static_code_valid_from
    ):
        raise Conflict("口令失效时间必须晚于生效时间", code="invalid_static_code_window")


def _validate_publishable(event: Event) -> None:
    if not any(
        (event.require_qr, event.require_static_code, event.require_gps, event.require_ip, event.require_face)
    ):
        raise Conflict("至少需要启用一种考勤校验方式", code="attendance_method_required")
    if event.require_gps and (event.latitude is None or event.longitude is None):
        raise Conflict("启用 GPS 考勤时必须设置活动经纬度", code="location_missing")
    if event.require_static_code and not event.static_code_hash:
        raise Conflict("启用静态口令时必须设置 6 位口令", code="static_code_required")


async def _ensure_capacity(session: AsyncSession, event: Event) -> None:
    active = await session.scalar(
        select(func.count(Registration.id)).where(
            Registration.event_id == event.id,
            Registration.status.in_(ACTIVE_REGISTRATION_STATUSES),
        )
    )
    if int(active or 0) > event.capacity:
        raise Conflict(
            f"名额上限不能小于当前报名人数（{active}）",
            code="capacity_below_registrations",
            details={"registered": int(active or 0)},
        )


async def _registration_stats(
    session: AsyncSession, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[RegistrationStatus, int]]:
    if not event_ids:
        return {}
    rows = (
        await session.execute(
            select(Registration.event_id, Registration.status, func.count(Registration.id))
            .where(Registration.event_id.in_(event_ids))
            .group_by(Registration.event_id, Registration.status)
        )
    ).all()
    result: dict[uuid.UUID, dict[RegistrationStatus, int]] = {}
    for event_id, status, count in rows:
        result.setdefault(event_id, {})[status] = int(count)
    return result
