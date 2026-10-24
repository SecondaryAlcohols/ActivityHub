from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_attendee
from app.core.config import settings
from app.core.errors import AppError
from app.db import get_db
from app.models.attendee import Attendee
from app.schemas.common import ApiResponse
from app.schemas.mp import (
    AttendeeOut,
    MpLoginResult,
    ProfileUpdate,
    WebLoginRequest,
)
from app.services import mp_auth_service

router = APIRouter(prefix="/attendee/auth", tags=["网页参与者认证"])


@router.post("/login", response_model=ApiResponse[MpLoginResult])
async def web_login(
    payload: WebLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not settings.web_demo_login:
        raise AppError(403, "网页体验登录未开启", 40300)
    ip = request.client.host if request.client else None
    result = await mp_auth_service.web_login(db, payload, ip)
    return ApiResponse(data=result)


@router.get("/me", response_model=ApiResponse[AttendeeOut])
async def me(attendee: Attendee = Depends(get_current_attendee)):
    return ApiResponse(data=AttendeeOut.model_validate(attendee))


@router.put("/profile", response_model=ApiResponse[AttendeeOut])
async def update_profile(
    payload: ProfileUpdate,
    attendee: Attendee = Depends(get_current_attendee),
    db: AsyncSession = Depends(get_db),
):
    if payload.is_empty():
        return ApiResponse(data=AttendeeOut.model_validate(attendee))
    attendee = await mp_auth_service.update_profile(db, attendee, payload)
    return ApiResponse(data=AttendeeOut.model_validate(attendee))
