from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_attendee
from app.db import get_db
from app.models.attendee import Attendee
from app.schemas.common import ApiResponse
from app.schemas.mp import AttendeeOut, MpLoginRequest, MpLoginResult, ProfileUpdate
from app.services import mp_auth_service

router = APIRouter(prefix="/mp/auth", tags=["小程序认证"])


@router.post("/login", response_model=ApiResponse[MpLoginResult])
async def login(
    payload: MpLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    result = await mp_auth_service.login(db, payload, ip)
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
