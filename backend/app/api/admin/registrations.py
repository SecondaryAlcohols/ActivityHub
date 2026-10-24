from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_roles
from app.db import get_db
from app.models.admin_user import AdminUser
from app.schemas.common import ApiResponse, Page
from app.schemas.registration import (
    AdminRegistrationDetail,
    AdminRegistrationItem,
    BatchReviewResult,
    RegistrationBatchReview,
    RegistrationOut,
    RegistrationReview,
    RegistrationStats,
)
from app.services import activity_service, registration_service

router = APIRouter(
    prefix="/admin",
    tags=["报名管理"],
    dependencies=[Depends(require_roles("super_admin", "operator"))],
)


@router.get(
    "/activities/{activity_id}/registrations",
    response_model=ApiResponse[Page[AdminRegistrationItem]],
)
async def list_registrations(
    activity_id: int,
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    items, total = await registration_service.list_registrations(
        db,
        activity=activity,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=Page(items=items, total=total, page=page, page_size=page_size)
    )


@router.get(
    "/activities/{activity_id}/stats",
    response_model=ApiResponse[RegistrationStats],
)
async def get_stats(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
):
    activity = await activity_service.get_activity(db, activity_id)
    stats = await registration_service.get_stats(db, activity)
    return ApiResponse(data=stats)


@router.get(
    "/registrations/{registration_id}",
    response_model=ApiResponse[AdminRegistrationDetail],
)
async def get_registration(
    registration_id: int,
    db: AsyncSession = Depends(get_db),
):
    detail = await registration_service.get_registration_detail(db, registration_id)
    return ApiResponse(data=detail)


@router.post(
    "/registrations/{registration_id}/review",
    response_model=ApiResponse[RegistrationOut],
)
async def review_registration(
    registration_id: int,
    payload: RegistrationReview,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    registration = await registration_service.review_registration(
        db,
        registration_id=registration_id,
        payload=payload,
        admin=admin,
        ip=ip,
    )
    return ApiResponse(data=RegistrationOut.model_validate(registration))


@router.post(
    "/registrations/batch-review",
    response_model=ApiResponse[BatchReviewResult],
)
async def batch_review_registrations(
    payload: RegistrationBatchReview,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await registration_service.batch_review_registrations(
        db, payload=payload, admin=admin, ip=ip
    )
    return ApiResponse(data=result)


@router.post(
    "/registrations/{registration_id}/cancel",
    response_model=ApiResponse[RegistrationOut],
)
async def admin_cancel_registration(
    registration_id: int,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    registration = await registration_service.admin_cancel_registration(
        db, registration_id=registration_id, admin=admin, ip=ip
    )
    return ApiResponse(data=RegistrationOut.model_validate(registration))
