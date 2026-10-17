from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.activity import Activity
from app.models.admin_user import AdminUser
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.services.audit import write_audit_log


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
    if activity.status in ("closed", "finished"):
        raise AppError(409, "已下架或已结束的活动不能修改", 40902)

    for field, value in payload.model_dump().items():
        setattr(activity, field, value)

    write_audit_log(
        db,
        admin_id=admin.id,
        action="activity.update",
        target_type="activity",
        target_id=activity.id,
        detail={"title": activity.title},
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
    if activity.status != "draft":
        raise AppError(409, "只有草稿活动可以发布", 40904)

    activity.status = "published"
    activity.published_at = datetime.now()
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
    if activity.status != "published":
        raise AppError(409, "只有已发布的活动可以下架", 40905)

    activity.status = "closed"
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
    if activity.status != "published":
        raise AppError(409, "只有已发布的活动可以结束", 40906)

    activity.status = "finished"
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
