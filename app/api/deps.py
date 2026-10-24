"""FastAPI 依赖：认证、鉴权、分页。"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Forbidden, Unauthorized
from app.core.http import get_client_ip
from app.core.pagination import PageParams
from app.core.security import decode_token
from app.db.session import SessionFactory, get_db
from app.models.enums import UserRole
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False, description="Bearer 访问令牌")

DbSession = Annotated[AsyncSession, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def page_params(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
) -> PageParams:
    return PageParams(page=page, size=size)


PageQuery = Annotated[PageParams, Depends(page_params)]


def client_ip(request: Request) -> str:
    return get_client_ip(request)


async def _load_user(session: AsyncSession, token: str) -> User:
    payload = decode_token(token, expected_type="access")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise Unauthorized("凭证内容不合法", code="invalid_token") from exc

    user = await session.get(User, user_id)
    if user is None:
        raise Unauthorized("账号不存在", code="invalid_token")
    if not user.is_active:
        raise Forbidden("账号已被停用", code="account_disabled")
    return user


async def get_current_user(
    session: DbSession, credentials: Credentials
) -> User:
    if credentials is None:
        raise Unauthorized("请先登录")
    return await _load_user(session, credentials.credentials)


async def get_optional_user(
    session: DbSession, credentials: Credentials
) -> User | None:
    if credentials is None:
        return None
    try:
        return await _load_user(session, credentials.credentials)
    except (Unauthorized, Forbidden):
        return None


async def get_user_snapshot(credentials: Credentials) -> User:
    """长连接（SSE）使用：会话关闭后仍可读取用户基础字段。"""
    if credentials is None:
        raise Unauthorized("请先登录")
    payload = decode_token(credentials.credentials, expected_type="access")
    async with SessionFactory() as session:
        user = await session.get(User, uuid.UUID(payload["sub"]))
        if user is None or not user.is_active:
            raise Unauthorized("账号不可用", code="invalid_token")
        return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
UserSnapshot = Annotated[User, Depends(get_user_snapshot)]
ClientIp = Annotated[str, Depends(client_ip)]


def require_roles(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise Forbidden("当前账号无权访问该资源")
        return user

    return _dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
OrganizerUser = Annotated[User, Depends(require_roles(UserRole.ORGANIZER, UserRole.ADMIN))]
