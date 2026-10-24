"""报名业务逻辑：名额原子扣减、状态流转、审核与统计。"""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.ticket import generate_ticket_token
from app.models.activity import Activity
from app.models.admin_user import AdminUser
from app.models.attendee import Attendee
from app.models.registration import Registration
from app.schemas.registration import (
    ActivityBrief,
    AdminRegistrationDetail,
    AdminRegistrationItem,
    AttendeeBrief,
    BatchReviewResult,
    RegistrationBatchReview,
    RegistrationReview,
    RegistrationStats,
    TicketOut,
)
from app.services.audit import write_audit_log
from app.services.form_validation import validate_answers

ACTIVE_STATUSES = ("pending", "approved")

_REASON_ERRORS: dict[str, tuple[int, str, int]] = {
    "activity_closed": (409, "活动当前不可报名", 40914),
    "not_started": (409, "报名尚未开始", 40912),
    "closed": (409, "报名已截止", 40913),
    "full": (409, "名额已满", 40911),
    "already_registered": (409, "请勿重复报名", 40910),
}


def _raise_for_reason(reason: str) -> None:
    status_code, message, code = _REASON_ERRORS.get(
        reason, (409, "活动当前不可报名", 40914)
    )
    raise AppError(status_code, message, code)


def _remaining(activity: Activity) -> int:
    return max(0, activity.capacity - activity.taken_count)


def compute_signup_state(
    activity: Activity, registration: Registration | None, now: datetime
) -> tuple[bool, str | None]:
    if activity.status != "published":
        return False, "activity_closed"
    if registration is not None and registration.status in ACTIVE_STATUSES:
        return False, "already_registered"
    if now < activity.signup_start_at:
        return False, "not_started"
    if now > activity.signup_end_at:
        return False, "closed"
    if activity.taken_count >= activity.capacity:
        return False, "full"
    return True, None


async def find_registration(
    db: AsyncSession, activity_id: int, attendee_id: int
) -> Registration | None:
    return await db.scalar(
        select(Registration).where(
            Registration.activity_id == activity_id,
            Registration.attendee_id == attendee_id,
        )
    )


async def get_published_activity(db: AsyncSession, activity_id: int) -> Activity:
    activity = await db.get(Activity, activity_id)
    if activity is None or activity.status != "published":
        raise AppError(404, "活动不存在或已下架", 40401)
    return activity


async def list_published_activities(
    db: AsyncSession,
    *,
    tab: str | None,
    page: int,
    page_size: int,
    now: datetime | None = None,
) -> tuple[list[Activity], int]:
    now = now or datetime.now()
    conditions = [Activity.status == "published"]
    order_by = (Activity.start_at.asc(), Activity.id.asc())

    if tab == "upcoming":
        conditions.append(Activity.start_at > now)
    elif tab == "ongoing":
        conditions.append(Activity.start_at <= now)
        conditions.append(Activity.end_at >= now)
    elif tab == "past":
        conditions.append(Activity.end_at < now)
        order_by = (Activity.start_at.desc(), Activity.id.desc())

    total = await db.scalar(
        select(func.count()).select_from(Activity).where(*conditions)
    )
    result = await db.scalars(
        select(Activity)
        .where(*conditions)
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), int(total or 0)


async def _occupy_capacity(db: AsyncSession, activity_id: int, now: datetime) -> bool:
    """条件更新占用一个名额；返回是否成功。"""
    result = await db.execute(
        update(Activity)
        .where(
            Activity.id == activity_id,
            Activity.status == "published",
            Activity.signup_start_at <= now,
            Activity.signup_end_at >= now,
            Activity.taken_count < Activity.capacity,
        )
        .values(
            taken_count=Activity.taken_count + 1,
            version=Activity.version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


async def _release_capacity(db: AsyncSession, activity_id: int) -> None:
    await db.execute(
        update(Activity)
        .where(Activity.id == activity_id, Activity.taken_count > 0)
        .values(
            taken_count=Activity.taken_count - 1,
            version=Activity.version + 1,
        )
        .execution_options(synchronize_session=False)
    )


async def create_registration(
    db: AsyncSession,
    *,
    activity_id: int,
    attendee: Attendee,
    answers: dict[str, Any],
    ip: str | None = None,
) -> Registration:
    activity = await db.get(Activity, activity_id)
    if activity is None:
        raise AppError(404, "活动不存在", 40401)

    attendee_id = attendee.id
    now = datetime.now()
    existing = await find_registration(db, activity_id, attendee_id)
    can_signup, reason = compute_signup_state(activity, existing, now)
    if not can_signup:
        _raise_for_reason(reason or "activity_closed")

    cleaned, name, phone = validate_answers(activity.form_schema, answers)
    new_status = "pending" if activity.need_review else "approved"

    if not await _occupy_capacity(db, activity_id, now):
        await db.rollback()
        fresh = await db.get(Activity, activity_id)
        if fresh is None:
            raise AppError(404, "活动不存在", 40401)
        fresh_existing = await find_registration(db, activity_id, attendee_id)
        _, fresh_reason = compute_signup_state(fresh, fresh_existing, now)
        _raise_for_reason(fresh_reason or "full")

    if existing is None:
        registration = Registration(
            activity_id=activity_id,
            attendee_id=attendee_id,
            status=new_status,
            answers=cleaned,
            applicant_name=name,
            applicant_phone=phone,
        )
        db.add(registration)
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise AppError(409, "请勿重复报名", 40910) from exc
    else:
        reused = await db.execute(
            update(Registration)
            .where(
                Registration.id == existing.id,
                Registration.status.in_(("cancelled", "rejected")),
            )
            .values(
                status=new_status,
                answers=cleaned,
                applicant_name=name,
                applicant_phone=phone,
                cancelled_at=None,
                reviewed_by=None,
                reviewed_at=None,
                review_note=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if reused.rowcount != 1:
            await db.rollback()
            raise AppError(409, "请勿重复报名", 40910)
        registration = await db.scalar(
            select(Registration)
            .where(Registration.id == existing.id)
            .execution_options(populate_existing=True)
        )

    attendee.phone = phone
    write_audit_log(
        db,
        admin_id=None,
        action="registration.create",
        target_type="registration",
        target_id=registration.id if registration else None,
        detail={
            "activity_id": activity_id,
            "attendee_id": attendee_id,
            "status": new_status,
        },
        ip=ip,
    )
    await db.commit()
    await db.refresh(registration)
    return registration


async def list_my_registrations(
    db: AsyncSession,
    *,
    attendee_id: int,
    status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[Registration, Activity]], int]:
    conditions = [Registration.attendee_id == attendee_id]
    if status:
        conditions.append(Registration.status == status)

    total = await db.scalar(
        select(func.count()).select_from(Registration).where(*conditions)
    )
    rows = await db.execute(
        select(Registration, Activity)
        .join(Activity, Activity.id == Registration.activity_id)
        .where(*conditions)
        .order_by(Registration.created_at.desc(), Registration.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [(row[0], row[1]) for row in rows.all()], int(total or 0)


async def get_owned_registration(
    db: AsyncSession, registration_id: int, attendee: Attendee
) -> tuple[Registration, Activity]:
    registration = await db.get(Registration, registration_id)
    if registration is None:
        raise AppError(404, "报名记录不存在", 40402)
    if registration.attendee_id != attendee.id:
        raise AppError(403, "没有权限查看该报名", 40300)

    activity = await db.get(Activity, registration.activity_id)
    if activity is None:
        raise AppError(404, "活动不存在", 40401)
    return registration, activity


async def cancel_registration(
    db: AsyncSession,
    *,
    registration: Registration,
    activity: Activity,
    attendee_id: int,
    ip: str | None = None,
) -> Registration:
    now = datetime.now()
    if registration.attendee_id != attendee_id:
        raise AppError(403, "没有权限操作该报名", 40300)
    if registration.status not in ACTIVE_STATUSES:
        raise AppError(409, "该报名当前不可取消", 40915)
    if activity.status != "published":
        raise AppError(409, "活动当前不可取消报名", 40914)
    if not activity.allow_cancel:
        raise AppError(409, "活动不允许取消报名", 40915)
    deadline = activity.cancel_deadline or activity.signup_end_at
    if now > deadline:
        raise AppError(409, "已超过取消截止时间", 40915)

    cancelled = await db.execute(
        update(Registration)
        .where(
            Registration.id == registration.id,
            Registration.status.in_(ACTIVE_STATUSES),
        )
        .values(status="cancelled", cancelled_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if cancelled.rowcount != 1:
        await db.rollback()
        raise AppError(409, "该报名当前不可取消", 40915)

    await _release_capacity(db, registration.activity_id)
    write_audit_log(
        db,
        admin_id=None,
        action="registration.cancel",
        target_type="registration",
        target_id=registration.id,
        detail={"activity_id": registration.activity_id, "attendee_id": attendee_id},
        ip=ip,
    )
    await db.commit()
    return await db.scalar(
        select(Registration)
        .where(Registration.id == registration.id)
        .execution_options(populate_existing=True)
    )


async def build_ticket(
    db: AsyncSession, registration: Registration, activity: Activity
) -> TicketOut:
    if registration.status not in ACTIVE_STATUSES:
        raise AppError(409, "报名已取消或未通过审核，无法出示电子票", 40915)
    return TicketOut(
        token=generate_ticket_token(registration.id, activity.id),
        registration_id=registration.id,
        activity_id=activity.id,
        activity_title=activity.title,
        applicant_name=registration.applicant_name,
        status=registration.status,
        start_at=activity.start_at,
        end_at=activity.end_at,
        location_name=activity.location_name,
    )


async def list_registrations(
    db: AsyncSession,
    *,
    activity: Activity,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[AdminRegistrationItem], int]:
    if activity.status == "draft":
        raise AppError(409, "草稿活动还没有报名记录", 40921)

    conditions = [Registration.activity_id == activity.id]
    if status:
        conditions.append(Registration.status == status)
    if keyword:
        conditions.append(
            or_(
                Registration.applicant_name.contains(keyword, autoescape=True),
                Registration.applicant_phone.contains(keyword, autoescape=True),
            )
        )

    total = await db.scalar(
        select(func.count()).select_from(Registration).where(*conditions)
    )
    rows = await db.execute(
        select(Registration, Attendee.nickname)
        .join(Attendee, Attendee.id == Registration.attendee_id)
        .where(*conditions)
        .order_by(Registration.created_at.desc(), Registration.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items = []
    for registration, nickname in rows.all():
        item = AdminRegistrationItem.model_validate(registration)
        item.attendee_nickname = nickname or ""
        items.append(item)
    return items, int(total or 0)


async def get_registration_detail(
    db: AsyncSession, registration_id: int
) -> AdminRegistrationDetail:
    registration = await db.get(Registration, registration_id)
    if registration is None:
        raise AppError(404, "报名记录不存在", 40402)
    activity = await db.get(Activity, registration.activity_id)
    if activity is None:
        raise AppError(404, "活动不存在", 40401)
    attendee = await db.get(Attendee, registration.attendee_id)

    detail = AdminRegistrationDetail(
        **AdminRegistrationItem.model_validate(registration).model_dump(),
        activity=ActivityBrief.model_validate(activity),
        form_schema=activity.form_schema,
    )
    if attendee is not None:
        detail.attendee = AttendeeBrief.model_validate(attendee)
    return detail


async def _apply_review(
    db: AsyncSession,
    *,
    registration: Registration,
    approve: bool,
    note: str | None,
    admin: AdminUser,
    ip: str | None,
) -> bool:
    now = datetime.now()
    new_status = "approved" if approve else "rejected"
    result = await db.execute(
        update(Registration)
        .where(
            Registration.id == registration.id,
            Registration.status == "pending",
        )
        .values(
            status=new_status,
            reviewed_by=admin.id,
            reviewed_at=now,
            review_note=(note or "").strip() or None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return False

    if not approve:
        await _release_capacity(db, registration.activity_id)

    write_audit_log(
        db,
        admin_id=admin.id,
        action="registration.review",
        target_type="registration",
        target_id=registration.id,
        detail={
            "activity_id": registration.activity_id,
            "status": new_status,
            "note": (note or "").strip() or None,
        },
        ip=ip,
    )
    return True


async def review_registration(
    db: AsyncSession,
    *,
    registration_id: int,
    payload: RegistrationReview,
    admin: AdminUser,
    ip: str | None,
) -> Registration:
    registration = await db.get(Registration, registration_id)
    if registration is None:
        raise AppError(404, "报名记录不存在", 40402)
    if registration.status != "pending":
        raise AppError(409, "该报名不在待审核状态", 40917)

    approve = payload.action == "approve"
    if not await _apply_review(
        db,
        registration=registration,
        approve=approve,
        note=payload.note,
        admin=admin,
        ip=ip,
    ):
        await db.rollback()
        raise AppError(409, "该报名不在待审核状态", 40917)

    await db.commit()
    return await db.scalar(
        select(Registration)
        .where(Registration.id == registration_id)
        .execution_options(populate_existing=True)
    )


async def batch_review_registrations(
    db: AsyncSession,
    *,
    payload: RegistrationBatchReview,
    admin: AdminUser,
    ip: str | None,
) -> BatchReviewResult:
    result = BatchReviewResult()
    approve = payload.action == "approve"

    for registration_id in dict.fromkeys(payload.ids):
        registration = await db.get(Registration, registration_id)
        if registration is None or registration.status != "pending":
            result.skipped += 1
            continue
        if await _apply_review(
            db,
            registration=registration,
            approve=approve,
            note=payload.note,
            admin=admin,
            ip=ip,
        ):
            if approve:
                result.approved += 1
            else:
                result.rejected += 1
        else:
            result.skipped += 1

    await db.commit()
    return result


async def admin_cancel_registration(
    db: AsyncSession,
    *,
    registration_id: int,
    admin: AdminUser,
    ip: str | None,
) -> Registration:
    registration = await db.get(Registration, registration_id)
    if registration is None:
        raise AppError(404, "报名记录不存在", 40402)
    if registration.status not in ACTIVE_STATUSES:
        raise AppError(409, "该报名当前不可取消", 40915)

    now = datetime.now()
    cancelled = await db.execute(
        update(Registration)
        .where(
            Registration.id == registration_id,
            Registration.status.in_(ACTIVE_STATUSES),
        )
        .values(status="cancelled", cancelled_at=now, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if cancelled.rowcount != 1:
        await db.rollback()
        raise AppError(409, "该报名当前不可取消", 40915)

    await _release_capacity(db, registration.activity_id)
    write_audit_log(
        db,
        admin_id=admin.id,
        action="registration.admin_cancel",
        target_type="registration",
        target_id=registration_id,
        detail={"activity_id": registration.activity_id},
        ip=ip,
    )
    await db.commit()
    return await db.scalar(
        select(Registration)
        .where(Registration.id == registration_id)
        .execution_options(populate_existing=True)
    )


async def get_stats(db: AsyncSession, activity: Activity) -> RegistrationStats:
    rows = await db.execute(
        select(Registration.status, func.count())
        .where(Registration.activity_id == activity.id)
        .group_by(Registration.status)
    )
    counts = {status: int(count) for status, count in rows.all()}
    total = sum(counts.values())
    rate = round(activity.taken_count * 100 / activity.capacity) if activity.capacity else 0

    return RegistrationStats(
        total=total,
        pending=counts.get("pending", 0),
        approved=counts.get("approved", 0),
        rejected=counts.get("rejected", 0),
        cancelled=counts.get("cancelled", 0),
        capacity=activity.capacity,
        remaining=_remaining(activity),
        signup_rate=rate,
    )
