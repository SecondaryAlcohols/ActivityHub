"""认证服务：注册、登录、令牌刷新与注销。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import Conflict, Forbidden, Unauthorized
from app.core.security import (
    burn_password_check,
    create_token,
    decode_token,
    hash_secret,
    verify_secret,
)
from app.models.enums import UserRole
from app.models.user import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.utils.time import utcnow


async def register(session: AsyncSession, payload: RegisterRequest) -> User:
    conditions = [User.student_no == payload.student_no]
    if payload.phone:
        conditions.append(User.phone == payload.phone)

    exists = await session.scalar(select(User.id).where(or_(*conditions)))
    if exists:
        raise Conflict("学号或手机号已被注册", code="account_exists")

    user = User(
        student_no=payload.student_no,
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        college=payload.college,
        role=UserRole.STUDENT,
        password_hash=await asyncio.to_thread(hash_secret, payload.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("学号或手机号已被注册", code="account_exists") from exc
    await session.refresh(user)
    return user


async def login(
    session: AsyncSession,
    payload: LoginRequest,
    *,
    ip: str | None,
    user_agent: str | None,
) -> TokenPair:
    account = payload.account.strip()
    statement = select(User).where(
        or_(User.student_no == account.upper(), User.phone == account)
    )
    user = await session.scalar(statement)

    if user is None:
        await asyncio.to_thread(burn_password_check)
        raise Unauthorized("账号或密码错误", code="invalid_credentials")

    password_ok = await asyncio.to_thread(verify_secret, payload.password, user.password_hash)
    if not password_ok:
        raise Unauthorized("账号或密码错误", code="invalid_credentials")
    if not user.is_active:
        raise Forbidden("账号已被停用，请联系管理员", code="account_disabled")

    tokens = await issue_tokens(session, user, ip=ip, user_agent=user_agent)
    user.last_login_at = utcnow()
    await session.commit()
    return tokens


async def issue_tokens(
    session: AsyncSession,
    user: User,
    *,
    ip: str | None,
    user_agent: str | None,
) -> TokenPair:
    settings = get_settings()
    access, _, _ = create_token(
        subject=str(user.id),
        token_type="access",
        role=user.role.value,
        ttl=timedelta(minutes=settings.access_token_ttl_minutes),
    )
    refresh, jti, expires_at = create_token(
        subject=str(user.id),
        token_type="refresh",
        role=user.role.value,
        ttl=timedelta(days=settings.refresh_token_ttl_days),
    )
    session.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip=ip,
            created_at=utcnow(),
        )
    )
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_minutes * 60,
        refresh_expires_in=settings.refresh_token_ttl_days * 86400,
    )


async def refresh_tokens(
    session: AsyncSession,
    refresh_token: str,
    *,
    ip: str | None,
    user_agent: str | None,
) -> TokenPair:
    claims = decode_token(refresh_token, expected_type="refresh")
    jti = claims.get("jti", "")

    # 行锁保证并发刷新时只有一个请求能成功轮换
    statement = select(RefreshToken).where(RefreshToken.jti == jti).with_for_update()
    stored = await session.scalar(statement)
    if stored is None or stored.revoked_at is not None:
        raise Unauthorized("刷新令牌已失效，请重新登录", code="refresh_token_revoked")
    if stored.expires_at < utcnow():
        raise Unauthorized("刷新令牌已过期，请重新登录", code="refresh_token_expired")

    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise Unauthorized("账号不可用", code="account_disabled")

    stored.revoked_at = utcnow()
    tokens = await issue_tokens(session, user, ip=ip, user_agent=user_agent)
    await session.commit()
    return tokens


async def logout(session: AsyncSession, refresh_token: str) -> None:
    try:
        claims = decode_token(refresh_token, expected_type="refresh")
    except Unauthorized:
        return  # 幂等：无效令牌直接视为已注销
    stored = await session.scalar(select(RefreshToken).where(RefreshToken.jti == claims.get("jti", "")))
    if stored and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        await session.commit()


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)
