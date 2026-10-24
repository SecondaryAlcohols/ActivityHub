"""用户端活动浏览与详情。"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.core.pagination import Page, PageParams
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceKind, EventStatus, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import Organization, User
from app.schemas.event import EventDetail, EventListItem, MyAttendance
from app.schemas.user import AttendanceProgress
from app.services.event_common import (
    ACTIVE_REGISTRATION_STATUSES,
    build_policy,
    compute_phase,
    mask_phone,
    methods_of,
)
from app.utils.time import utcnow


def _active_count_subquery():
    return (
        select(func.count(Registration.id))
        .where(
            Registration.event_id == Event.id,
            Registration.status.in_(ACTIVE_REGISTRATION_STATUSES),
        )
        .correlate(Event)
        .scalar_subquery()
    )


def _my_status_subquery(user_id: uuid.UUID):
    return (
        select(Registration.status)
        .where(Registration.event_id == Event.id, Registration.user_id == user_id)
        .correlate(Event)
        .scalar_subquery()
    )


async def list_events(
    session: AsyncSession,
    user: User | None,
    *,
    q: str | None,
    scope: str,
    params: PageParams,
) -> Page[EventListItem]:
    now = utcnow()
    user_id = user.id if user else uuid.UUID(int=0)
    active_count = _active_count_subquery()
    my_status = _my_status_subquery(user_id)

    conditions = [Event.status == EventStatus.PUBLISHED]
    if scope == "upcoming":
        conditions.append(Event.end_at >= now)
    elif scope == "past":
        conditions.append(Event.end_at < now)
    if q:
        keyword = f"%{q.strip()}%"
        conditions.append(
            or_(
                Event.title.ilike(keyword),
                Event.location_name.ilike(keyword),
                Organization.name.ilike(keyword),
            )
        )

    base = select(Event, Organization, active_count, my_status).join(
        Organization, Event.org_id == Organization.id
    )
    total = await session.scalar(
        select(func.count(Event.id)).select_from(Event).join(
            Organization, Event.org_id == Organization.id
        ).where(*conditions)
    )

    order = Event.start_at.desc() if scope == "past" else Event.start_at.asc()
    rows = (
        await session.execute(
            base.where(*conditions).order_by(order).offset(params.offset).limit(params.size)
        )
    ).all()

    event_ids = [row[0].id for row in rows]
    progress_map = await _progress_map(session, user_id, event_ids)

    items = [
        _to_list_item(
            event=row[0],
            org=row[1],
            active_count=row[2],
            my_status=row[3],
            now=now,
            progress=progress_map.get(row[0].id),
        )
        for row in rows
    ]
    return Page.build(items, int(total or 0), params)


async def get_event_detail(
    session: AsyncSession, user: User | None, event_id: uuid.UUID
) -> EventDetail:
    row = (
        await session.execute(
            select(Event, Organization, _active_count_subquery())
            .join(Organization, Event.org_id == Organization.id)
            .where(Event.id == event_id, Event.status == EventStatus.PUBLISHED)
        )
    ).first()
    if row is None:
        raise NotFound("活动不存在或未发布", code="event_not_found")

    event, org, active_count = row
    now = utcnow()
    registration = None
    records = []
    if user is not None:
        registration = await session.scalar(
            select(Registration).where(
                Registration.event_id == event.id, Registration.user_id == user.id
            )
        )
        records = (
            await session.scalars(
                select(AttendanceRecord).where(
                    AttendanceRecord.event_id == event.id, AttendanceRecord.user_id == user.id
                )
            )
        ).all()
    by_kind = {record.kind: record for record in records}
    checkin = by_kind.get(AttendanceKind.CHECKIN)
    checkout = by_kind.get(AttendanceKind.CHECKOUT)

    progress = _progress(event, checkin, checkout)
    my_attendance = MyAttendance(
        checkin_at=checkin.occurred_at if checkin else None,
        checkout_at=checkout.occurred_at if checkout else None,
        duration_minutes=_duration_minutes(checkin, checkout),
    )
    can_register, reason, message = _register_blocker(
        event=event,
        now=now,
        active_count=active_count,
        my_status=registration.status if registration else None,
    )

    host = org.contact_name or org.name
    if org.contact_phone:
        host = f"{host} · {mask_phone(org.contact_phone)}"

    return EventDetail(
        **_to_list_item(
            event=event,
            org=org,
            active_count=active_count,
            my_status=registration.status if registration else None,
            now=now,
            progress=progress,
        ).model_dump(),
        description=event.description,
        latitude=event.latitude,
        longitude=event.longitude,
        policy=build_policy(event),
        host_contact=host,
        my_registration=(
            {
                "id": registration.id,
                "status": registration.status,
                "ticket_code": registration.ticket_code,
            }
            if registration
            else None
        ),
        my_attendance=my_attendance,
        can_register=can_register,
        register_blocked_reason=reason,
        register_blocked_message=message,
    )


def _to_list_item(
    *,
    event: Event,
    org: Organization,
    active_count: int,
    my_status: RegistrationStatus | None,
    now,
    progress: AttendanceProgress | None,
) -> EventListItem:
    remaining = max(0, event.capacity - int(active_count or 0))
    return EventListItem(
        id=event.id,
        title=event.title,
        organization=org.name,
        location_name=event.location_name,
        cover_color=event.cover_color,
        start_at=event.start_at,
        end_at=event.end_at,
        registration_deadline=event.registration_deadline,
        capacity=event.capacity,
        registered_count=int(active_count or 0),
        remaining=remaining,
        phase=compute_phase(event, now),
        is_full=remaining == 0,
        requires_approval=event.requires_approval,
        methods=methods_of(event),
        my_registration_status=my_status,
        my_attendance_progress=progress.value if progress else None,
    )


def _register_blocker(
    *,
    event: Event,
    now,
    active_count: int,
    my_status: RegistrationStatus | None,
) -> tuple[bool, str | None, str | None]:
    if my_status == RegistrationStatus.APPROVED:
        return False, "already_registered", "你已报名该活动"
    if my_status == RegistrationStatus.PENDING:
        return False, "registration_pending", "报名正在审核中"
    if now > event.registration_deadline:
        return False, "registration_closed", "报名已截止"
    if int(active_count or 0) >= event.capacity:
        return False, "event_full", "名额已满"
    if now > event.end_at:
        return False, "event_ended", "活动已结束"
    return True, None, None


async def _progress_map(
    session: AsyncSession, user_id: uuid.UUID, event_ids: list[uuid.UUID]
) -> dict[uuid.UUID, AttendanceProgress]:
    if not event_ids:
        return {}
    records = (
        await session.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.user_id == user_id, AttendanceRecord.event_id.in_(event_ids)
            )
        )
    ).all()
    grouped: dict[uuid.UUID, dict[AttendanceKind, AttendanceRecord]] = {}
    for record in records:
        grouped.setdefault(record.event_id, {})[record.kind] = record

    result: dict[uuid.UUID, AttendanceProgress] = {}
    for event_id, kinds in grouped.items():
        checkin = kinds.get(AttendanceKind.CHECKIN)
        checkout = kinds.get(AttendanceKind.CHECKOUT)
        if checkin and checkout:
            result[event_id] = AttendanceProgress.COMPLETED
        elif checkin:
            result[event_id] = AttendanceProgress.PENDING_CHECKOUT
    return result


def _progress(
    event: Event, checkin: AttendanceRecord | None, checkout: AttendanceRecord | None
) -> AttendanceProgress | None:
    if checkin and checkout:
        return AttendanceProgress.COMPLETED
    if checkin and not event.requires_checkout:
        return AttendanceProgress.COMPLETED
    if checkin:
        return AttendanceProgress.PENDING_CHECKOUT
    return None


def _duration_minutes(
    checkin: AttendanceRecord | None, checkout: AttendanceRecord | None
) -> int | None:
    if not checkin or not checkout:
        return None
    delta: timedelta = checkout.occurred_at - checkin.occurred_at
    return max(0, int(delta.total_seconds() // 60))
