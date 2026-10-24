from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.activity import Activity
from app.models.admin_user import AdminUser
from app.schemas.activity import ActivityCreate, ActivityUpdate, FormField
from app.services.audit import write_audit_log


def _same_datetime(left: datetime | None, right: datetime | None) -> bool:
    # 时间按本地时间无时区存储，比较时忽略时区与微秒差异
    if left is None or right is None:
        return left is None and right is None
    return left.replace(tzinfo=None, microsecond=0) == right.replace(
        tzinfo=None, microsecond=0
    )


def _schema_snapshot(schema: list) -> list[dict]:
    return [FormField.model_validate(field).model_dump() for field in schema]


async def list_activities(
    db: AsyncSession,
    *,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Activity], int]:
    conditions = []
    if status:
        conditions.append(Activity.status == status)
    if keyword:
        conditions.append(
            Activity.title.contains(keyword, autoescape=True)
            | Activity.location_name.contains(keyword, autoescape=True)
        )

    total = await db.scalar(
        select(func.count()).select_from(Activity).where(*conditions)
    )
    result = await db.scalars(
        select(Activity)
        .where(*conditions)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result), int(total or 0)


async def get_activity(db: AsyncSession, activity_id: int) -> Activity:
    activity = await db.get(Activity, activity_id)
    if activity is None:
        raise AppError(404, "活动不存在", 40401)
    return activity


async def _lock_activity(db: AsyncSession, activity_id: int) -> Activity:
    activity = await db.scalar(
        select(Activity)
        .where(Activity.id == activity_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if activity is None:
        raise AppError(404, "活动不存在", 40401)
    return activity


async def create_activity(
    db: AsyncSession,
    payload: ActivityCreate,
    admin: AdminUser,
    ip: str | None,
) -> Activity:
    activity = Activity(
        **payload.model_dump(),
        created_by=admin.id,
        status="draft",
        taken_count=0,
    )
    db.add(activity)
    await db.flush()
    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.create",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
        ip=ip,
    )
    await db.commit()
    await db.refresh(activity)
    return activity


async def update_activity(
    db: AsyncSession,
    activity: Activity,
    payload: ActivityUpdate,
    admin: AdminUser,
    ip: str | None,
) -> Activity:
    activity = await _lock_activity(db, activity.id)

    if activity.status in ("closed", "finished"):
        raise AppError(409, "已下架或已结束的活动不能修改", 40902)

    if payload.version != activity.version:
        raise AppError(409, "活动已被其他人修改，请刷新后重试", 40907)

    if payload.capacity < activity.taken_count:
        raise AppError(
            409,
            f"报名名额不能少于已报名人数（当前 {activity.taken_count} 人）",
            40908,
        )

    if activity.taken_count > 0:
        if _schema_snapshot(activity.form_schema) != [
            field.model_dump() for field in payload.form_schema
        ]:
            raise AppError(409, "活动已有报名，报名表单不可修改", 40909)
        if not _same_datetime(
            payload.signup_start_at, activity.signup_start_at
        ) or not _same_datetime(payload.signup_end_at, activity.signup_end_at):
            raise AppError(409, "活动已有报名，报名时间不可修改", 40916)

    updates = payload.model_dump(exclude={"version"})
    for field, value in updates.items():
        setattr(activity, field, value)
    activity.version += 1

    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.update",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title, "version": activity.version},
        ip=ip,
    )
    await db.commit()
    await db.refresh(activity)
    return activity


async def delete_activity(
    db: AsyncSession,
    activity: Activity,
    admin: AdminUser,
    ip: str | None,
) -> None:
    activity = await _lock_activity(db, activity.id)

    if activity.status != "draft":
        raise AppError(409, "只有草稿活动可以删除", 40903)

    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.delete",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
        ip=ip,
    )
    await db.delete(activity)
    await db.commit()


async def publish_activity(
    db: AsyncSession,
    activity: Activity,
    admin: AdminUser,
    ip: str | None,
) -> Activity:
    activity = await _lock_activity(db, activity.id)

    if activity.status != "draft":
        raise AppError(409, "只有草稿活动可以发布", 40904)

    activity.status = "published"
    activity.published_at = datetime.now()
    activity.version += 1
    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.publish",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
        ip=ip,
    )
    await db.commit()
    await db.refresh(activity)
    return activity


async def close_activity(
    db: AsyncSession,
    activity: Activity,
    admin: AdminUser,
    ip: str | None,
) -> Activity:
    activity = await _lock_activity(db, activity.id)

    if activity.status != "published":
        raise AppError(409, "只有已发布的活动可以下架", 40905)

    activity.status = "closed"
    activity.version += 1
    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.close",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
        ip=ip,
    )
    await db.commit()
    await db.refresh(activity)
    return activity


async def finish_activity(
    db: AsyncSession,
    activity: Activity,
    admin: AdminUser,
    ip: str | None,
) -> Activity:
    activity = await _lock_activity(db, activity.id)

    if activity.status != "published":
        raise AppError(409, "只有已发布的活动可以结束", 40906)

    activity.status = "finished"
    activity.version += 1
    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.finish",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
        ip=ip,
    )
    await db.commit()
    await db.refresh(activity)
    return activity
