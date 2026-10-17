from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def write_audit_log(
    db: AsyncSession,
    *,
    admin_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        AuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip=ip,
        )
    )
