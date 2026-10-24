"""静态口令校验：时间窗限制 + Argon2 哈希比对。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.core.security import verify_secret
from app.models.event import Event
from app.services.checkin.base import CheckinError, VerificationContext


def resolve_static_window(event: Event) -> tuple[datetime, datetime]:
    """未显式配置时，口令整场考勤窗口内有效。"""
    start = event.static_code_valid_from or event.checkin_opens_at
    end = event.static_code_valid_to or event.checkin_closes_at
    return start, end


async def verify(ctx: VerificationContext) -> None:
    event = ctx.event
    if not ctx.payload.static_code:
        raise CheckinError("static_code_required", "请输入组织者公布的静态口令")

    valid_from, valid_to = resolve_static_window(event)
    if ctx.now < valid_from:
        raise CheckinError(
            "static_code_not_open",
            "静态口令尚未生效",
            {"valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat()},
        )
    if ctx.now > valid_to:
        raise CheckinError(
            "static_code_window_closed",
            "静态口令已失效",
            {"valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat()},
        )

    matched = await asyncio.to_thread(verify_secret, ctx.payload.static_code, event.static_code_hash)
    if not matched:
        raise CheckinError("static_code_invalid", "静态口令不正确")

    ctx.passed_methods.append("static_code")
