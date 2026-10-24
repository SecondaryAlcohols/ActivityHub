"""考勤校验流水线：按配置逐项执行，任一不通过即中断。

顺序上先校验"在场证明"（二维码/口令），再校验位置与网络，最后执行开销最大
的人脸比对，避免无效的远程调用。
"""

from __future__ import annotations

from app.services.checkin import face, geo, ip, qr, static_code
from app.services.checkin.base import CheckinError, VerificationContext
from app.services.checkin.static_code import resolve_static_window

__all__ = [
    "CheckinError",
    "VerificationContext",
    "resolve_static_window",
    "run",
]


async def run(ctx: VerificationContext) -> VerificationContext:
    if ctx.event.require_qr:
        await qr.verify(ctx)
    if ctx.event.require_static_code:
        await static_code.verify(ctx)
    if ctx.event.require_gps:
        await geo.verify(ctx)
    if ctx.event.require_ip:
        await ip.verify(ctx)
    if ctx.event.require_face:
        await face.verify(ctx)
    return ctx
