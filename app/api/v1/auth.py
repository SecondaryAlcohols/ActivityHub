"""认证相关接口。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClientIp, CurrentUser, DbSession
from app.core.config import get_settings
from app.core.exceptions import RateLimited
from app.core.ratelimit import SlidingWindowLimiter
from app.models.user import FaceTemplate, User
from app.schemas.auth import (
    FaceEnrollRequest,
    FaceEnrollResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserProfile,
)
from app.schemas.common import MessageResponse
from app.schemas.user import FaceStatus
from app.services import auth as auth_service
from app.services import face as face_service

router = APIRouter(prefix="/auth", tags=["认证"])

_settings = get_settings()

# 同一 IP + 账号限流，抵御撞库；同一 IP 总量限流，抵御广撒网
login_limiter = SlidingWindowLimiter(
    limit=_settings.login_rate_limit, window_seconds=_settings.login_rate_window_seconds
)
ip_login_limiter = SlidingWindowLimiter(
    limit=_settings.ip_login_rate_limit, window_seconds=_settings.login_rate_window_seconds
)
# 注册接口按 IP 限制，避免批量注册
register_limiter = SlidingWindowLimiter(
    limit=_settings.register_rate_limit, window_seconds=_settings.register_rate_window_seconds
)


async def _profile(session: AsyncSession, user: User) -> UserProfile:
    has_face = await session.scalar(
        select(FaceTemplate.user_id).where(FaceTemplate.user_id == user.id)
    ) is not None
    return UserProfile(
        id=user.id,
        student_no=user.student_no,
        name=user.name,
        phone=user.phone,
        email=user.email,
        college=user.college,
        role=user.role,
        has_face=has_face,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="学生注册",
)
async def register(payload: RegisterRequest, session: DbSession, ip: ClientIp) -> UserProfile:
    allowed, retry_after = await register_limiter.hit(ip)
    if not allowed:
        raise RateLimited(
            "注册过于频繁，请稍后再试",
            code="register_rate_limited",
            details={"retry_after_seconds": retry_after},
        )
    user = await auth_service.register(session, payload)
    return await _profile(session, user)


@router.post("/login", response_model=TokenPair, summary="登录")
async def login(
    payload: LoginRequest,
    session: DbSession,
    ip: ClientIp,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenPair:
    key = f"{ip}:{payload.account}"
    allowed, retry_after = await login_limiter.hit(key)
    if not allowed:
        raise RateLimited(
            "登录尝试过于频繁，请稍后再试",
            code="login_rate_limited",
            details={"retry_after_seconds": retry_after},
        )
    ip_allowed, ip_retry_after = await ip_login_limiter.hit(ip)
    if not ip_allowed:
        raise RateLimited(
            "当前网络登录尝试过于频繁，请稍后再试",
            code="login_rate_limited",
            details={"retry_after_seconds": ip_retry_after},
        )
    tokens = await auth_service.login(session, payload, ip=ip, user_agent=user_agent)
    await login_limiter.reset(key)
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="刷新令牌")
async def refresh(
    payload: RefreshRequest,
    session: DbSession,
    ip: ClientIp,
    user_agent: Annotated[str | None, Header()] = None,
) -> TokenPair:
    return await auth_service.refresh_tokens(
        session, payload.refresh_token, ip=ip, user_agent=user_agent
    )


@router.post("/logout", response_model=MessageResponse, summary="退出登录")
async def logout(payload: RefreshRequest, session: DbSession) -> MessageResponse:
    await auth_service.logout(session, payload.refresh_token)
    return MessageResponse(message="已退出登录")


@router.get("/me", response_model=UserProfile, summary="当前用户信息")
async def me(user: CurrentUser, session: DbSession) -> UserProfile:
    return await _profile(session, user)


@router.get("/face", response_model=FaceStatus, summary="人脸录入状态")
async def face_status(user: CurrentUser, session: DbSession) -> FaceStatus:
    return await face_service.get_status(session, user.id)


@router.put("/face", response_model=FaceEnrollResponse, summary="录入/更新人脸")
async def enroll_face(
    payload: FaceEnrollRequest, user: CurrentUser, session: DbSession, ip: ClientIp
) -> FaceEnrollResponse:
    return await face_service.enroll(session, user, payload.image, ip)


@router.get("/config", summary="客户端可见的认证配置")
async def auth_config() -> dict:
    settings = get_settings()
    return {
        "access_token_ttl_minutes": settings.access_token_ttl_minutes,
        "refresh_token_ttl_days": settings.refresh_token_ttl_days,
        "qr_default_rotation_seconds": settings.qr_default_rotation_seconds,
    }
