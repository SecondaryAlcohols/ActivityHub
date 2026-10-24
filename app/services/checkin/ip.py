"""IP 校验：限制在校园网/指定网段内。"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.checkin.base import CheckinError, VerificationContext
from app.utils.geo import ip_in_networks


async def verify(ctx: VerificationContext) -> None:
    allowed = ctx.event.allowed_ip_cidrs or get_settings().campus_cidrs
    if not ip_in_networks(ctx.client_ip, allowed):
        raise CheckinError(
            "ip_not_allowed",
            "当前网络不在允许的网段内，请连接校园网后重试",
            {"ip": ctx.client_ip, "allowed_cidrs": allowed},
        )
    ctx.passed_methods.append("ip")
