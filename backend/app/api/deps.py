from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_token
from app.db import get_db
from app.models.admin_user import AdminUser
from app.models.attendee import Attendee

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise AppError(401, "请先登录", 40100)

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "admin":
        raise AppError(403, "没有权限执行此操作", 40300)

    try:
        admin_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(401, "无效的登录凭证", 40102) from exc

    admin = await db.get(AdminUser, admin_id)
    if admin is None or not admin.status:
        raise AppError(401, "账号不存在或已被禁用", 40104)
    return admin


async def get_current_attendee(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Attendee:
    if credentials is None:
        raise AppError(401, "请先登录", 40100)

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "attendee":
        raise AppError(401, "无效的登录凭证", 40102)

    try:
        attendee_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(401, "无效的登录凭证", 40102) from exc

    attendee = await db.get(Attendee, attendee_id)
    if attendee is None:
        raise AppError(401, "账号不存在，请重新登录", 40104)
    return attendee


async def get_optional_attendee(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Attendee | None:
    """公开接口使用：有合法小程序 Token 时返回用户，否则按未登录处理。"""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except AppError:
        return None
    if payload.get("type") != "attendee":
        return None
    try:
        attendee_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    return await db.get(Attendee, attendee_id)


def require_roles(*roles: str):
    async def dependency(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in roles:
            raise AppError(403, "没有权限执行此操作", 40300)
        return admin

    return dependency
