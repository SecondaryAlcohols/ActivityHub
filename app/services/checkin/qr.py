"""动态二维码校验：签名 + 有效期 + 单用户单次使用。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.security import constant_time_equals, verify_qr_token
from app.models.qr import QrChallenge, QrUsage
from app.services.checkin.base import CheckinError, VerificationContext


async def verify(ctx: VerificationContext) -> None:
    payload = ctx.payload
    if not payload.qr_token and not payload.qr_code:
        raise CheckinError("qr_required", "请扫描现场动态二维码")

    challenge = await _resolve_challenge(ctx, payload.qr_token, payload.qr_code)
    if challenge is None:
        raise CheckinError("qr_invalid", "二维码无效，请重新扫描")

    if challenge.expires_at <= ctx.now:
        raise CheckinError("qr_expired", "二维码已过期，请扫描大屏最新二维码")

    if payload.qr_token and not verify_qr_token(
        payload.qr_token, challenge.nonce, str(ctx.event.id), challenge.expires_at
    ):
        raise CheckinError("qr_invalid", "二维码签名校验失败")

    # 原子占用：同一用户对同一 challenge 只能使用一次，防截图重放
    statement = (
        pg_insert(QrUsage)
        .values(
            challenge_id=challenge.id,
            user_id=ctx.user.id,
            kind=ctx.kind,
            used_at=ctx.now,
        )
        .on_conflict_do_nothing(index_elements=["challenge_id", "user_id", "kind"])
        .returning(QrUsage.id)
    )
    result = await ctx.session.execute(statement)
    if result.scalar_one_or_none() is None:
        raise CheckinError("qr_already_used", "该二维码已用于本次考勤，请扫描最新二维码")

    ctx.passed_methods.append("qr")


async def _resolve_challenge(
    ctx: VerificationContext, token: str | None, code: str | None
) -> QrChallenge | None:
    if code:
        # 手输口令：只认当前活动最新一条 challenge，避免枚举历史口令
        statement = (
            select(QrChallenge)
            .where(QrChallenge.event_id == ctx.event.id)
            .order_by(QrChallenge.issued_at.desc())
            .limit(1)
        )
        challenge = await ctx.session.scalar(statement)
        if challenge is None:
            return None
        if not constant_time_equals(challenge.code, code):
            raise CheckinError("qr_invalid", "动态口令不正确")
        return challenge

    if not token:
        return None
    nonce = token.split(".", 1)[0]
    challenge = await ctx.session.scalar(select(QrChallenge).where(QrChallenge.nonce == nonce))
    if challenge is None or challenge.event_id != ctx.event.id:
        return None
    return challenge
