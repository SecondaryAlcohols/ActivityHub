from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db import get_db
from app.models.admin_user import AdminUser
from app.schemas.auth import (
    AdminOut,
    ChangePasswordRequest,
    LoginRequest,
    LoginResult,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/admin/auth", tags=["后台认证"])


@router.post("/login", response_model=ApiResponse[LoginResult])
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await auth_service.login(db, payload, ip)
    return ApiResponse(data=result)


@router.get("/me", response_model=ApiResponse[AdminOut])
async def me(admin: AdminUser = Depends(get_current_admin)):
    return ApiResponse(data=AdminOut.model_validate(admin))


@router.put("/password", response_model=ApiResponse[None])
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    await auth_service.change_password(db, admin, payload, ip)
    return ApiResponse(data=None)
