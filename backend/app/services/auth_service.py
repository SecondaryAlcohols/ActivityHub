from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import (
    record_failure,
    reset_attempts,
    seconds_until_allowed,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.admin_user import AdminUser
from app.schemas.auth import AdminOut, ChangePasswordRequest, LoginRequest, LoginResult
from app.services.audit import write_audit_log


def _login_key(ip: str | None, username: str) -> str:
    return f"{ip or 'unknown'}:{username.strip().lower()}"


async def login(db: AsyncSession, payload: LoginRequest, ip: str | None) -> LoginResult:
    key = _login_key(ip, payload.username)
    window_seconds = settings.login_window_minutes * 60
    remaining = seconds_until_allowed(key, window_seconds)
    if remaining > 0:
        minutes = max(1, (remaining + 59) // 60)
        raise AppError(429, f"登录失败次数过多，请 {minutes} 分钟后再试", 42901)

    admin = await db.scalar(
        select(AdminUser).where(AdminUser.username == payload.username)
    )
    if admin is None or not verify_password(admin.password_hash, payload.password):
        record_failure(
            key,
            settings.login_max_attempts,
            window_seconds,
            settings.login_lock_minutes * 60,
        )
        raise AppError(401, "用户名或密码错误", 40103)
    if not admin.status:
        raise AppError(403, "账号已被禁用", 40301)

    reset_attempts(key)
    admin.last_login_at = datetime.now()
    write_audit_log(
        db,
        admin_id=admin.id,
        action="auth.login",
        target_type="admin_user",
        target_id=admin.id,
        ip=ip,
    )
    await db.commit()
    await db.refresh(admin)

    return LoginResult(
        access_token=create_access_token(admin.id, admin.role),
        admin=AdminOut.model_validate(admin),
    )


async def change_password(
    db: AsyncSession,
    admin: AdminUser,
    payload: ChangePasswordRequest,
    ip: str | None,
) -> None:
    if not verify_password(admin.password_hash, payload.old_password):
        raise AppError(400, "原密码不正确", 40001)

    admin.password_hash = hash_password(payload.new_password)
    write_audit_log(
        db,
        admin_id=admin.id,
        action="auth.change_password",
        target_type="admin_user",
        target_id=admin.id,
        ip=ip,
    )
    await db.commit()
