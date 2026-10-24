"""报名流程：报名、取消、审核与电子票。"""

from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import Conflict, Forbidden, NotFound
from app.core.security import sign_payload
from app.models.attendance import AttendanceRecord
from app.models.enums import AuditAction, EventStatus, RegistrationStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.schemas.registration import MyRegistrations, RegistrationResult, TicketOut
from app.schemas.user import MyRegistrationItem
from app.services import audit
from app.services.event_common import ACTIVE_REGISTRATION_STATUSES
from app.utils.time import utcnow

TICKET_TTL_AFTER_EVENT = timedelta(days=1)


async def register(session: AsyncSession, user: User, event_id: uuid.UUID) -> RegistrationResult:
    # 对活动行加锁，串行化名额判定，杜绝并发超卖
    event = await session.scalar(select(Event).where(Event.id == event_id).with_for_update())
    if event is None or event.status != EventStatus.PUBLISHED:
        raise NotFound("活动不存在或未发布", code="event_not_found")

    now = utcnow()
    if now > event.registration_deadline:
        raise Conflict("报名已截止", code="registration_closed")
    if now > event.end_at:
        raise Conflict("活动已结束", code="event_ended")

    existing = await session.scalar(
        select(Registration).where(
            Registration.event_id == event.id, Registration.user_id == user.id
        )
    )
    if existing and existing.status in ACTIVE_REGISTRATION_STATUSES:
        raise Conflict(
            "你已报名该活动",
            code="already_registered",
            details={"status": existing.status.value, "registration_id": str(existing.id)},
        )

    active_count = await session.scalar(
        select(func.count(Registration.id)).where(
            Registration.event_id == event.id,
            Registration.status.in_(ACTIVE_REGISTRATION_STATUSES),
        )
    )
    if int(active_count or 0) >= event.capacity:
        raise Conflict("名额已满", code="event_full")

    target_status = (
        RegistrationStatus.PENDING if event.requires_approval else RegistrationStatus.APPROVED
    )

    if existing is None:
        registration = Registration(
            event_id=event.id,
            user_id=user.id,
            status=target_status,
            ticket_code=secrets.token_hex(8).upper(),
            applied_at=now,
        )
        session.add(registration)
    else:
        # 曾取消/被拒后重新报名：复用同一行与电子票编号
        registration = existing
        registration.status = target_status
        registration.applied_at = now
        registration.cancelled_at = None
        registration.reject_reason = None
        registration.reviewed_at = None
        registration.reviewed_by = None

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("你已报名该活动", code="already_registered") from exc

    return RegistrationResult(
        id=registration.id,
        event_id=registration.event_id,
        status=registration.status,
        ticket_code=registration.ticket_code,
        applied_at=registration.applied_at,
        requires_approval=event.requires_approval,
        message="报名成功" if not event.requires_approval else "已提交报名，等待组织者审核",
    )


async def cancel(session: AsyncSession, user: User, registration_id: uuid.UUID, ip: str | None) -> None:
    row = (
        await session.execute(
            select(Registration)
            .options(joinedload(Registration.event))
            .where(Registration.id == registration_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("报名记录不存在", code="registration_not_found")
    if row.user_id != user.id:
        raise Forbidden("不能操作他人的报名记录")

    if row.status not in ACTIVE_REGISTRATION_STATUSES:
        raise Conflict("该报名当前状态不可取消", code="invalid_registration_status")
    if row.event.start_at <= utcnow():
        raise Conflict("活动已开始，无法取消报名", code="event_started")

    checked_in = await session.scalar(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.registration_id == row.id,
            AttendanceRecord.kind == "checkin",
        )
    )
    if checked_in:
        raise Conflict("已签到，无法取消报名", code="already_checked_in")

    row.status = RegistrationStatus.CANCELLED
    row.cancelled_at = utcnow()
    await audit.record(
        session,
        actor=user,
        action=AuditAction.REGISTRATION_CANCELLED,
        target_type="registration",
        target_id=row.id,
        payload={"event_id": str(row.event_id)},
        ip=ip,
    )
    await session.commit()


async def list_my_registrations(session: AsyncSession, user: User) -> MyRegistrations:
    rows = (
        await session.execute(
            select(Registration)
            .options(joinedload(Registration.event))
            .where(Registration.user_id == user.id)
            .order_by(Registration.applied_at.desc())
        )
    ).scalars().all()

    items = [
        MyRegistrationItem(
            id=row.id,
            event_id=row.event.id,
            event_title=row.event.title,
            cover_color=row.event.cover_color,
            location_name=row.event.location_name,
            start_at=row.event.start_at,
            end_at=row.event.end_at,
            status=row.status,
            applied_at=row.applied_at,
            reject_reason=row.reject_reason,
            ticket_code=row.ticket_code,
        )
        for row in rows
    ]
    return MyRegistrations(items=items, total=len(items))


async def build_ticket(session: AsyncSession, user: User, registration_id: uuid.UUID) -> TicketOut:
    row = (
        await session.execute(
            select(Registration)
            .options(joinedload(Registration.event))
            .where(Registration.id == registration_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("报名记录不存在", code="registration_not_found")
    if row.user_id != user.id:
        raise Forbidden("不能查看他人的电子票")
    if row.status not in ACTIVE_REGISTRATION_STATUSES:
        raise Conflict("报名未生效，暂无电子票", code="ticket_unavailable")

    valid_until = row.event.end_at + TICKET_TTL_AFTER_EVENT
    token = sign_payload(
        {
            "typ": "ticket",
            "rid": str(row.id),
            "uid": str(user.id),
            "eid": str(row.event_id),
            "code": row.ticket_code,
            "exp": int(valid_until.timestamp()),
        }
    )
    return TicketOut(
        ticket_token=token,
        ticket_code=row.ticket_code,
        event_id=row.event_id,
        event_title=row.event.title,
        holder_name=user.name,
        student_no=user.student_no,
        valid_until=valid_until,
    )


async def approve(
    session: AsyncSession, actor: User, registration_id: uuid.UUID, ip: str | None
) -> Registration:
    row = await _load_for_review(session, registration_id)
    if row.status != RegistrationStatus.PENDING:
        raise Conflict("该报名不处于待审核状态", code="invalid_registration_status")

    row.status = RegistrationStatus.APPROVED
    row.reviewed_at = utcnow()
    row.reviewed_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.REGISTRATION_APPROVED,
        target_type="registration",
        target_id=row.id,
        payload={"event_id": str(row.event_id), "user_id": str(row.user_id)},
        ip=ip,
    )
    await session.commit()
    return row


async def reject(
    session: AsyncSession,
    actor: User,
    registration_id: uuid.UUID,
    reason: str,
    ip: str | None,
) -> Registration:
    row = await _load_for_review(session, registration_id)
    if row.status != RegistrationStatus.PENDING:
        raise Conflict("该报名不处于待审核状态", code="invalid_registration_status")

    row.status = RegistrationStatus.REJECTED
    row.reject_reason = reason
    row.reviewed_at = utcnow()
    row.reviewed_by = actor.id
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.REGISTRATION_REJECTED,
        target_type="registration",
        target_id=row.id,
        payload={"event_id": str(row.event_id), "reason": reason},
        ip=ip,
    )
    await session.commit()
    return row


async def _load_for_review(session: AsyncSession, registration_id: uuid.UUID) -> Registration:
    row = await session.get(Registration, registration_id)
    if row is None:
        raise NotFound("报名记录不存在", code="registration_not_found")
    return row
