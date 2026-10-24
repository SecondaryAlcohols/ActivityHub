import logging
import re
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import create_attendee_token
from app.models.attendee import Attendee
from app.schemas.mp import (
    AttendeeOut,
    MpLoginRequest,
    MpLoginResult,
    ProfileUpdate,
    WebLoginRequest,
)

logger = logging.getLogger(__name__)

MOCK_PREFIX = "mock:"
MOCK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


class WechatError(AppError):
    def __init__(self, message: str, code: int = 50201):
        super().__init__(503, message, code)


def _mock_openid(code: str) -> str:
    suffix = code[len(MOCK_PREFIX) :].strip()
    if not MOCK_NAME_RE.match(suffix):
        raise AppError(400, "Mock 登录 code 不合法，格式为 mock:用户名", 40001)
    return f"mock_{suffix.lower()}"


async def _code2session(code: str) -> tuple[str, str | None]:
    if not settings.wechat_appid or not settings.wechat_secret:
        raise AppError(503, "微信登录尚未配置，请联系管理员", 50301)

    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    url = f"{settings.wechat_api_base.rstrip('/')}/sns/jscode2session"
    try:
        async with httpx.AsyncClient(timeout=settings.wechat_timeout_seconds) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("微信 code2session 请求失败: %s", exc)
        raise WechatError("微信登录服务暂时不可用，请稍后重试") from exc

    openid = data.get("openid")
    if not openid:
        logger.info(
            "微信 code2session 返回错误 errcode=%s errmsg=%s",
            data.get("errcode"),
            data.get("errmsg"),
        )
        raise AppError(401, "微信登录失败，请重新进入小程序", 40105)
    return str(openid), data.get("unionid")


async def login(
    db: AsyncSession, payload: MpLoginRequest, ip: str | None = None
) -> MpLoginResult:
    code = payload.code.strip()

    if settings.wechat_mock_login:
        if not code.startswith(MOCK_PREFIX):
            raise AppError(400, "开发环境 Mock 登录需要 mock: 前缀", 40002)
        openid = _mock_openid(code)
        unionid = None
    else:
        openid, unionid = await _code2session(code)

    attendee = await db.scalar(select(Attendee).where(Attendee.openid == openid))
    if attendee is None:
        attendee = Attendee(openid=openid, unionid=unionid, nickname="")
        db.add(attendee)
    elif unionid:
        attendee.unionid = unionid

    attendee.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(attendee)

    return MpLoginResult(
        access_token=create_attendee_token(attendee.id),
        attendee=AttendeeOut.model_validate(attendee),
    )


async def update_profile(
    db: AsyncSession, attendee: Attendee, payload: ProfileUpdate
) -> Attendee:
    if payload.nickname is not None:
        nickname = payload.nickname.strip()
        if not nickname:
            raise AppError(422, "昵称不能为空", 42200)
        attendee.nickname = nickname
    if payload.avatar_url is not None:
        attendee.avatar_url = payload.avatar_url.strip() or None

    await db.commit()
    await db.refresh(attendee)
    return attendee


async def web_login(
    db: AsyncSession, payload: WebLoginRequest, ip: str | None = None
) -> MpLoginResult:
    """网页体验登录：手机号作为身份标识，仅用于演示。"""
    nickname = payload.nickname.strip()
    phone = payload.phone.strip()
    if not nickname:
        raise AppError(422, "昵称不能为空", 42200)
    if not PHONE_RE.match(phone):
        raise AppError(422, "请输入有效的手机号", 42210)

    openid = f"web:{phone}"
    attendee = await db.scalar(select(Attendee).where(Attendee.openid == openid))
    if attendee is None:
        attendee = Attendee(openid=openid, nickname=nickname, phone=phone)
        db.add(attendee)
    else:
        attendee.nickname = nickname
        attendee.phone = phone

    attendee.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(attendee)

    return MpLoginResult(
        access_token=create_attendee_token(attendee.id),
        attendee=AttendeeOut.model_validate(attendee),
    )
