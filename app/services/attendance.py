"""考勤服务：上下文查询、签到/签退提交、异常检测与补签。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.exceptions import Conflict, NotFound, RateLimited
from app.db.session import SessionFactory
from app.models.anomaly import Anomaly
from app.models.attempt import CheckinAttempt
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
from app.models.user import FaceTemplate, User
from app.schemas.admin import ManualCheckinRequest
from app.schemas.attendance import (
    AnomalyNotice,
    AttendanceContext,
    AttendanceRecordOut,
    AttendanceResult,
    AttendanceState,
    CheckinRequest,
    StaticCodeWindow,
)
from app.services import audit, checkin
from app.services.checkin import CheckinError
from app.services.event_common import build_policy, verified_methods
from app.utils.time import seconds_until, utcnow


@dataclass(slots=True)
class WindowState:
    can_checkin: bool
    can_checkout: bool
    reason: str | None = None
    message: str | None = None


class _CtxIds:
    """回滚后仍可安全使用的原始 ID 快照。"""

    __slots__ = ("event_id", "registration_id", "user_id")

    def __init__(self, event_id: uuid.UUID, user_id: uuid.UUID, registration_id: uuid.UUID) -> None:
        self.event_id = event_id
        self.user_id = user_id
        self.registration_id = registration_id


async def get_context(
    session: AsyncSession,
    user: User,
    event_id: uuid.UUID,
    *,
    client_ip: str,
) -> AttendanceContext:
    event = await session.get(Event, event_id)
    if event is None or event.status == EventStatus.DRAFT:
        raise NotFound("活动不存在", code="event_not_found")

    registration = await session.scalar(
        select(Registration).where(
            Registration.event_id == event.id, Registration.user_id == user.id
        )
    )
    records = await _records_by_kind(session, registration.id if registration else None)
    has_face = await _has_face(session, user.id)
    now = utcnow()

    window = _evaluate(event, registration, records, now, has_face)
    checkin_record = records.get(AttendanceKind.CHECKIN)
    checkout_record = records.get(AttendanceKind.CHECKOUT)

    valid_from = event.static_code_valid_from or event.checkin_opens_at
    valid_to = event.static_code_valid_to or event.checkin_closes_at
    is_open = bool(event.require_static_code) and valid_from <= now <= valid_to

    return AttendanceContext(
        event_id=event.id,
        title=event.title,
        location_name=event.location_name,
        latitude=event.latitude,
        longitude=event.longitude,
        cover_color=event.cover_color,
        start_at=event.start_at,
        end_at=event.end_at,
        policy=build_policy(event),
        my_registration=(
            {
                "id": registration.id,
                "status": registration.status,
                "ticket_code": registration.ticket_code,
            }
            if registration
            else None
        ),
        attendance=AttendanceState(
            checked_in=checkin_record is not None,
            checked_out=checkout_record is not None,
            checkin_at=checkin_record.occurred_at if checkin_record else None,
            checkout_at=checkout_record.occurred_at if checkout_record else None,
            duration_minutes=_duration(checkin_record, checkout_record),
        ),
        static_code_window=StaticCodeWindow(
            valid_from=valid_from if event.require_static_code else None,
            valid_to=valid_to if event.require_static_code else None,
            is_open=is_open,
            remaining_seconds=seconds_until(valid_to, now=now) if is_open else 0,
        ),
        server_ip=client_ip,
        server_time=now,
        can_checkin=window.can_checkin,
        can_checkout=window.can_checkout,
        blocked_reason=window.reason,
        blocked_message=window.message,
        registration_status=registration.status if registration else None,
    )


async def submit(
    session: AsyncSession,
    user: User,
    event_id: uuid.UUID,
    kind: AttendanceKind,
    payload: CheckinRequest,
    *,
    client_ip: str,
    user_agent: str | None,
) -> AttendanceResult:
    event = await session.get(Event, event_id)
    if event is None or event.status == EventStatus.DRAFT:
        raise NotFound("活动不存在", code="event_not_found")
    if event.status == EventStatus.CANCELLED:
        raise CheckinError("event_cancelled", "活动已取消")

    registration = await session.scalar(
        select(Registration).where(
            Registration.event_id == event.id, Registration.user_id == user.id
        )
    )
    if registration is None:
        raise CheckinError("not_registered", "请先报名该活动")
    if registration.status == RegistrationStatus.PENDING:
        raise CheckinError("pending_approval", "报名仍在审核中，暂不能考勤")
    if registration.status == RegistrationStatus.REJECTED:
        raise CheckinError("registration_rejected", "报名未通过审核")
    if registration.status == RegistrationStatus.CANCELLED:
        raise CheckinError("registration_cancelled", "报名已取消")

    now = utcnow()
    ids = _CtxIds(event.id, user.id, registration.id)
    settings = get_settings()

    # 失败次数限制：滑动窗口，防止暴力猜口令/枚举二维码
    failure_count = await _recent_failure_count(session, ids, now)
    if failure_count >= settings.max_checkin_failures:
        raise RateLimited(
            f"考勤校验失败次数过多，请 {settings.checkin_failure_window_minutes} 分钟后再试",
            code="too_many_attempts",
        )

    existing = await session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.registration_id == registration.id,
            AttendanceRecord.kind == kind,
        )
    )
    if existing is not None:
        code = "already_checked_in" if kind == AttendanceKind.CHECKIN else "already_checked_out"
        message = "你已完成签到" if kind == AttendanceKind.CHECKIN else "你已完成签退"
        raise Conflict(message, code=code, details={"recorded_at": existing.occurred_at.isoformat()})

    has_face = await _has_face(session, user.id)
    records = await _records_by_kind(session, registration.id)
    _assert_action_allowed(event, records, kind, now, has_face)

    ctx = checkin.VerificationContext(
        session=session,
        event=event,
        registration=registration,
        user=user,
        kind=kind,
        payload=payload,
        client_ip=client_ip,
        user_agent=user_agent,
        now=now,
    )

    try:
        await checkin.run(ctx)
    except CheckinError as exc:
        # 丢弃本次事务中可能写入的二维码占用等数据，再独立记录失败流水
        await session.rollback()
        await _record_failure(ids, kind, exc.code, client_ip)
        await _maybe_flag_repeated_failures(ids, now)
        raise

    record = AttendanceRecord(
        event_id=ids.event_id,
        registration_id=ids.registration_id,
        user_id=ids.user_id,
        kind=kind,
        status=AttendanceStatus.NORMAL,
        occurred_at=now,
        verified_methods=ctx.passed_methods,
        is_manual=False,
        ip=client_ip,
        user_agent=(user_agent or "")[:255] or None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        distance_m=ctx.distance_m,
        accuracy_m=payload.accuracy_m,
        face_similarity=ctx.face_similarity,
        created_at=now,
    )
    session.add(record)
    await session.flush()

    notices = await _detect_same_ip(session, record, event, now)
    session.add(
        CheckinAttempt(
            event_id=ids.event_id,
            user_id=ids.user_id,
            kind=kind,
            success=True,
            failure_code=None,
            ip=client_ip,
            created_at=now,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        code = "already_checked_in" if kind == AttendanceKind.CHECKIN else "already_checked_out"
        raise Conflict("你已完成该项考勤", code=code) from exc

    state = AttendanceState(
        checked_in=True,
        checked_out=kind == AttendanceKind.CHECKOUT,
        checkin_at=now if kind == AttendanceKind.CHECKIN else None,
        checkout_at=now if kind == AttendanceKind.CHECKOUT else None,
    )
    if kind == AttendanceKind.CHECKOUT:
        checkin_record = records.get(AttendanceKind.CHECKIN)
        state.checkin_at = checkin_record.occurred_at if checkin_record else None
        state.duration_minutes = _duration(checkin_record, record)
    else:
        state.duration_minutes = None

    return AttendanceResult(
        record=to_record_out(record),
        state=state,
        anomalies=notices,
    )


async def manual_checkin(
    session: AsyncSession,
    actor: User,
    registration_id: uuid.UUID,
    payload: ManualCheckinRequest,
    *,
    ip: str | None,
) -> AttendanceRecord:
    row = (
        await session.execute(
            select(Registration)
            .options(joinedload(Registration.event), joinedload(Registration.user))
            .where(Registration.id == registration_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("报名记录不存在", code="registration_not_found")
    if row.status != RegistrationStatus.APPROVED:
        raise Conflict("仅已通过审核的报名可以补签", code="registration_not_approved")
    if payload.kind == AttendanceKind.CHECKOUT and not row.event.requires_checkout:
        raise Conflict("该活动无需签退", code="checkout_not_enabled")

    existing = await session.scalar(
        select(AttendanceRecord).where(
            AttendanceRecord.registration_id == row.id,
            AttendanceRecord.kind == payload.kind,
        )
    )
    if existing is not None:
        raise Conflict("该用户已完成该项考勤", code="attendance_exists")

    if payload.kind == AttendanceKind.CHECKOUT:
        checkin_exists = await session.scalar(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.registration_id == row.id,
                AttendanceRecord.kind == AttendanceKind.CHECKIN,
            )
        )
        if not checkin_exists:
            raise Conflict("该用户尚未签到，不能补签退", code="checkout_before_checkin")

    now = utcnow()
    occurred_at = payload.occurred_at or now
    if occurred_at > now:
        raise Conflict("补签时间不能晚于当前时间", code="invalid_occurred_at")

    record = AttendanceRecord(
        event_id=row.event_id,
        registration_id=row.id,
        user_id=row.user_id,
        kind=payload.kind,
        status=AttendanceStatus.FLAGGED,
        occurred_at=occurred_at,
        verified_methods=["manual"],
        is_manual=True,
        operator_id=actor.id,
        note=payload.reason,
        created_at=now,
    )
    session.add(record)
    await session.flush()

    # 补签属于人工干预，始终登记异常，便于事后复核
    session.add(
        Anomaly(
            event_id=row.event_id,
            user_id=row.user_id,
            attendance_record_id=record.id,
            type=AnomalyType.MANUAL_OVERRIDE,
            status=AnomalyStatus.OPEN,
            detail={
                "kind": payload.kind.value,
                "reason": payload.reason,
                "operator_id": str(actor.id),
                "operator_name": actor.name,
            },
            detected_at=now,
        )
    )
    await audit.record(
        session,
        actor=actor,
        action=AuditAction.MANUAL_CHECKIN,
        target_type="registration",
        target_id=row.id,
        payload={
            "kind": payload.kind.value,
            "reason": payload.reason,
            "occurred_at": occurred_at.isoformat(),
            "student_no": row.user.student_no,
        },
        ip=ip,
    )
    await session.commit()
    return record


# --------------------------------------------------------------------------- #
# 内部逻辑
# --------------------------------------------------------------------------- #
def _evaluate(
    event: Event,
    registration: Registration | None,
    records: dict[AttendanceKind, AttendanceRecord],
    now: datetime,
    has_face: bool,
) -> WindowState:
    if event.status == EventStatus.CANCELLED:
        return WindowState(False, False, "event_cancelled", "活动已取消")
    if registration is None:
        return WindowState(False, False, "not_registered", "请先报名该活动")
    if registration.status == RegistrationStatus.PENDING:
        return WindowState(False, False, "pending_approval", "报名审核中，暂不能考勤")
    if registration.status == RegistrationStatus.REJECTED:
        return WindowState(False, False, "registration_rejected", "报名未通过审核")
    if registration.status == RegistrationStatus.CANCELLED:
        return WindowState(False, False, "registration_cancelled", "报名已取消")
    if event.require_face and not has_face:
        return WindowState(False, False, "face_not_enrolled", "请先录入人脸信息")

    checked_in = AttendanceKind.CHECKIN in records
    checked_out = AttendanceKind.CHECKOUT in records

    can_checkin = False
    checkin_reason: tuple[str, str] | None = None
    if checked_in:
        checkin_reason = ("already_checked_in", "你已完成签到")
    elif now < event.checkin_opens_at:
        checkin_reason = ("checkin_not_open", "签到尚未开始")
    elif now > event.checkin_closes_at:
        checkin_reason = ("checkin_closed", "签到已结束")
    else:
        can_checkin = True

    can_checkout = False
    checkout_reason: tuple[str, str] | None = None
    if not event.requires_checkout:
        checkout_reason = ("checkout_not_enabled", "该活动无需签退")
    elif checked_out:
        checkout_reason = ("already_checked_out", "你已完成签退")
    elif not checked_in:
        checkout_reason = ("checkout_before_checkin", "请先完成签到")
    elif now > event.checkout_deadline_at:
        checkout_reason = ("checkout_closed", "签退已截止")
    else:
        can_checkout = True

    if can_checkin or can_checkout:
        return WindowState(can_checkin, can_checkout)

    # 都不满足时，优先返回签到相关原因
    reason, message = checkin_reason or checkout_reason or ("unavailable", "当前不可考勤")
    return WindowState(False, False, reason, message)


def _assert_action_allowed(
    event: Event,
    records: dict[AttendanceKind, AttendanceRecord],
    kind: AttendanceKind,
    now: datetime,
    has_face: bool,
) -> None:
    if event.require_face and not has_face:
        raise CheckinError("face_not_enrolled", "请先录入人脸信息")

    if kind == AttendanceKind.CHECKIN:
        if now < event.checkin_opens_at:
            raise CheckinError(
                "checkin_not_open",
                "签到尚未开始",
                {"opens_at": event.checkin_opens_at.isoformat()},
            )
        if now > event.checkin_closes_at:
            raise CheckinError(
                "checkin_closed",
                "签到已结束",
                {"closed_at": event.checkin_closes_at.isoformat()},
            )
        return

    if not event.requires_checkout:
        raise CheckinError("checkout_not_enabled", "该活动无需签退")
    if AttendanceKind.CHECKIN not in records:
        raise CheckinError("checkout_before_checkin", "请先完成签到")
    if now > event.checkout_deadline_at:
        raise CheckinError(
            "checkout_closed",
            "签退已截止",
            {"deadline_at": event.checkout_deadline_at.isoformat()},
        )


async def _records_by_kind(
    session: AsyncSession, registration_id: uuid.UUID | None
) -> dict[AttendanceKind, AttendanceRecord]:
    if registration_id is None:
        return {}
    rows = (
        await session.scalars(
            select(AttendanceRecord).where(AttendanceRecord.registration_id == registration_id)
        )
    ).all()
    return {row.kind: row for row in rows}


async def _has_face(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return await session.scalar(select(FaceTemplate.user_id).where(FaceTemplate.user_id == user_id)) is not None


async def _recent_failure_count(session: AsyncSession, ids: _CtxIds, now: datetime) -> int:
    window_start = now - timedelta(minutes=get_settings().checkin_failure_window_minutes)
    count = await session.scalar(
        select(func.count(CheckinAttempt.id)).where(
            CheckinAttempt.event_id == ids.event_id,
            CheckinAttempt.user_id == ids.user_id,
            CheckinAttempt.success.is_(False),
            CheckinAttempt.created_at >= window_start,
        )
    )
    return int(count or 0)


async def _record_failure(
    ids: _CtxIds, kind: AttendanceKind, code: str, client_ip: str
) -> None:
    """独立事务写失败流水，避免主事务回滚导致证据丢失。"""
    async with SessionFactory() as session:
        session.add(
            CheckinAttempt(
                event_id=ids.event_id,
                user_id=ids.user_id,
                kind=kind,
                success=False,
                failure_code=code,
                ip=client_ip,
                created_at=utcnow(),
            )
        )
        await session.commit()


async def _maybe_flag_repeated_failures(ids: _CtxIds, now: datetime) -> None:
    settings = get_settings()
    window_start = now - timedelta(minutes=settings.checkin_failure_window_minutes)

    async with SessionFactory() as session:
        count = await session.scalar(
            select(func.count(CheckinAttempt.id)).where(
                CheckinAttempt.event_id == ids.event_id,
                CheckinAttempt.user_id == ids.user_id,
                CheckinAttempt.success.is_(False),
                CheckinAttempt.created_at >= window_start,
            )
        )
        if int(count or 0) < settings.max_checkin_failures:
            return

        existing = await session.scalar(
            select(Anomaly.id).where(
                Anomaly.event_id == ids.event_id,
                Anomaly.user_id == ids.user_id,
                Anomaly.type == AnomalyType.FAILED_ATTEMPTS,
                Anomaly.status == AnomalyStatus.OPEN,
                Anomaly.detected_at >= window_start,
            )
        )
        if existing:
            return

        session.add(
            Anomaly(
                event_id=ids.event_id,
                user_id=ids.user_id,
                type=AnomalyType.FAILED_ATTEMPTS,
                status=AnomalyStatus.OPEN,
                detail={"failures": int(count or 0), "window_minutes": settings.checkin_failure_window_minutes},
                detected_at=now,
            )
        )
        await session.commit()


async def _detect_same_ip(
    session: AsyncSession,
    record: AttendanceRecord,
    event: Event,
    now: datetime,
) -> list[AnomalyNotice]:
    """同 IP 多账号签到：不阻断（校园 NAT 常见），但标记并生成预警。"""
    if not record.ip:
        return []
    window_start = now - timedelta(minutes=get_settings().same_ip_window_minutes)

    peers = (
        await session.execute(
            select(AttendanceRecord, User)
            .join(User, AttendanceRecord.user_id == User.id)
            .where(
                AttendanceRecord.event_id == event.id,
                AttendanceRecord.ip == record.ip,
                AttendanceRecord.id != record.id,
                AttendanceRecord.user_id != record.user_id,
                AttendanceRecord.created_at >= window_start,
            )
            .order_by(AttendanceRecord.created_at.desc())
            .limit(5)
        )
    ).all()
    if not peers:
        return []

    peer_record, peer_user = peers[0]
    record.status = AttendanceStatus.FLAGGED
    peer_record.status = AttendanceStatus.FLAGGED

    current_user_name = await session.scalar(select(User.name).where(User.id == record.user_id))
    if not await _has_open_anomaly(session, event.id, record.user_id, AnomalyType.SAME_IP, window_start):
        session.add(
            Anomaly(
                event_id=event.id,
                user_id=record.user_id,
                attendance_record_id=record.id,
                type=AnomalyType.SAME_IP,
                status=AnomalyStatus.OPEN,
                detail={
                    "ip": record.ip,
                    "window_minutes": get_settings().same_ip_window_minutes,
                    "peer_user_id": str(peer_user.id),
                    "peer_name": peer_user.name,
                    "peer_student_no": peer_user.student_no,
                },
                detected_at=now,
            )
        )

    if not await _has_open_anomaly(
        session, event.id, peer_record.user_id, AnomalyType.SAME_IP, window_start
    ):
        session.add(
            Anomaly(
                event_id=event.id,
                user_id=peer_record.user_id,
                attendance_record_id=peer_record.id,
                type=AnomalyType.SAME_IP,
                status=AnomalyStatus.OPEN,
                detail={
                    "ip": record.ip,
                    "window_minutes": get_settings().same_ip_window_minutes,
                    "peer_user_id": str(record.user_id),
                    "peer_name": current_user_name,
                    "peer_student_no": await session.scalar(
                        select(User.student_no).where(User.id == record.user_id)
                    ),
                },
                detected_at=now,
            )
        )

    return [
        AnomalyNotice(
            type="same_ip",
            message=f"与 {peer_user.name} 使用同一 IP，已记录待复核",
        )
    ]


async def _has_open_anomaly(
    session: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    anomaly_type: AnomalyType,
    since: datetime,
) -> bool:
    found = await session.scalar(
        select(Anomaly.id).where(
            Anomaly.event_id == event_id,
            Anomaly.user_id == user_id,
            Anomaly.type == anomaly_type,
            Anomaly.status == AnomalyStatus.OPEN,
            Anomaly.detected_at >= since,
        )
    )
    return found is not None


def to_record_out(record: AttendanceRecord) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=record.id,
        event_id=record.event_id,
        kind=record.kind,
        status=record.status,
        occurred_at=record.occurred_at,
        verified_methods=verified_methods(record.verified_methods),
        is_manual=record.is_manual,
        distance_m=record.distance_m,
        face_similarity=record.face_similarity,
        ip=record.ip,
        note=record.note,
    )


def _duration(
    checkin_record: AttendanceRecord | None, checkout_record: AttendanceRecord | None
) -> int | None:
    if not checkin_record or not checkout_record:
        return None
    return max(0, int((checkout_record.occurred_at - checkin_record.occurred_at).total_seconds() // 60))
