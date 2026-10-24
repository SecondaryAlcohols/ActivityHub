"""审计日志写入。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User
from app.utils.time import utcnow


async def record(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """写入审计日志（随调用方事务一起提交）。"""
    session.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            actor_role=actor.role.value if actor else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            payload=payload or {},
            ip=ip,
            created_at=utcnow(),
        )
    )
