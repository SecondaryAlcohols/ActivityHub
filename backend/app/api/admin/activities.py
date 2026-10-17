from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_roles
from app.db import get_db
from app.models.admin_user import AdminUser
from app.schemas.activity import (
    ActivityCreate,
    ActivityListItem,
    ActivityOut,
    ActivityStatus,
    ActivityUpdate,
)
from app.schemas.common import ApiResponse, Page
from app.services import activity_service

router = APIRouter(
    prefix="/admin/activities",
    tags=["活动管理"],
    dependencies=[Depends(require_roles("super_admin", "operator"))],
)


@router.get("", response_model=ApiResponse[Page[ActivityListItem]])
async def list_activities(
    status: ActivityStatus | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await activity_service.list_activities(
        db,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=Page(
            items=[ActivityListItem.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[ActivityOut])
async def create_activity(
    payload: ActivityCreate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    activity = await activity_service.create_activity(db, payload, admin, ip)
    return ApiResponse(data=ActivityOut.model_validate(activity))


@router.get("/{activity_id}", response_model=ApiResponse[ActivityOut])
async def get_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    return ApiResponse(data=ActivityOut.model_validate(activity))


@router.put("/{activity_id}", response_model=ApiResponse[ActivityOut])
async def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    ip = request.client.host if request.client else None
    activity = await activity_service.update_activity(db, activity, payload, admin, ip)
    return ApiResponse(data=ActivityOut.model_validate(activity))


@router.delete("/{activity_id}", response_model=ApiResponse[None])
async def delete_activity(
    activity_id: int,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    ip = request.client.host if request.client else None
    await activity_service.delete_activity(db, activity, admin, ip)
    return ApiResponse(data=None)


@router.post("/{activity_id}/publish", response_model=ApiResponse[ActivityOut])
async def publish_activity(
    activity_id: int,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    ip = request.client.host if request.client else None
    activity = await activity_service.publish_activity(db, activity, admin, ip)
    return ApiResponse(data=ActivityOut.model_validate(activity))


@router.post("/{activity_id}/close", response_model=ApiResponse[ActivityOut])
async def close_activity(
    activity_id: int,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    ip = request.client.host if request.client else None
    activity = await activity_service.close_activity(db, activity, admin, ip)
    return ApiResponse(data=ActivityOut.model_validate(activity))


@router.post("/{activity_id}/finish", response_model=ApiResponse[ActivityOut])
async def finish_activity(
    activity_id: int,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    ip = request.client.host if request.client else None
    activity = await activity_service.finish_activity(db, activity, admin, ip)
    return ApiResponse(data=ActivityOut.model_validate(activity))
