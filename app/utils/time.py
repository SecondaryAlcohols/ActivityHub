"""时间工具：数据库与对外输出统一使用 UTC。"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """把可能缺失时区的时间（如数据库驱动返回值）视为 UTC。"""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def seconds_until(moment: datetime | None, *, now: datetime | None = None) -> int:
    if moment is None:
        return 0
    current = now or utcnow()
    return max(0, int((ensure_utc(moment) - current).total_seconds()))
