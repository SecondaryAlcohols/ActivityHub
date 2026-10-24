"""个人中心：我的考勤记录。"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceKind, EventStatus
from app.models.event import Event
from app.models.user import User
from app.schemas.user import AttendanceProgress, MyAttendanceItem


async def my_attendance(session: AsyncSession, user: User) -> list[MyAttendanceItem]:
    rows = (
        await session.execute(
            select(AttendanceRecord, Event)
            .join(Event, AttendanceRecord.event_id == Event.id)
            .where(AttendanceRecord.user_id == user.id, Event.status != EventStatus.DRAFT)
            .order_by(Event.start_at.desc())
        )
    ).all()

    grouped: dict[uuid.UUID, dict[str, AttendanceRecord]] = defaultdict(dict)
    events: dict[uuid.UUID, Event] = {}
    for record, event in rows:
        grouped[event.id][record.kind.value] = record
        events[event.id] = event

    items: list[MyAttendanceItem] = []
    for event_id, kinds in grouped.items():
        event = events[event_id]
        checkin = kinds.get(AttendanceKind.CHECKIN.value)
        checkout = kinds.get(AttendanceKind.CHECKOUT.value)
        if (checkin and checkout) or (checkin and not event.requires_checkout):
            progress = AttendanceProgress.COMPLETED
        elif checkin:
            progress = AttendanceProgress.PENDING_CHECKOUT
        else:
            continue

        duration = None
        if checkin and checkout:
            duration = max(
                0,
                int((checkout.occurred_at - checkin.occurred_at).total_seconds() // 60),
            )
        items.append(
            MyAttendanceItem(
                event_id=event.id,
                registration_id=checkin.registration_id,
                event_title=event.title,
                cover_color=event.cover_color,
                start_at=event.start_at,
                end_at=event.end_at,
                checkin_at=checkin.occurred_at if checkin else None,
                checkout_at=checkout.occurred_at if checkout else None,
                duration_minutes=duration,
                progress=progress,
                requires_checkout=event.requires_checkout,
            )
        )
    return items
