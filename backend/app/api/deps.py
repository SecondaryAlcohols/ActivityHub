from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db import get_db
from app.models.admin_user import AdminUser

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise AppError(401, "请先登录", 40100)

    payload = decode_access_token(credentials.credentials)
    try:
        admin_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(401, "无效的登录凭证", 40102) from exc

    admin = await db.get(AdminUser, admin_id)
    if admin is None or not admin.status:
        raise AppError(401, "账号不存在或已被禁用", 40104)
    return admin


def require_roles(*roles: str):
    async def dependency(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in roles:
            raise AppError(403, "没有权限执行此操作", 40300)
        return admin

    return dependency
