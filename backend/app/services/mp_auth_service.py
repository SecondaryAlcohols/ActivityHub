import logging
import re
from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.rate_limit import (
    record_failure,
    reset_attempts,
    seconds_until_allowed,
)
from app.core.security import (
    create_attendee_token,
    hash_password,
    verify_password,
)
from app.models.attendee import Attendee
from app.schemas.mp import (
    AttendeeOut,
    MpLoginRequest,
    MpLoginResult,
    ProfileUpdate,
    WebPasswordLoginRequest,
    WebRegisterRequest,
)

logger = logging.getLogger(__name__)

MOCK_PREFIX = "mock:"
MOCK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


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


def _attendee_result(attendee: Attendee) -> MpLoginResult:
    return MpLoginResult(
        access_token=create_attendee_token(attendee.id),
        attendee=AttendeeOut.model_validate(attendee),
    )


async def register(
    db: AsyncSession, payload: WebRegisterRequest, ip: str | None = None
) -> MpLoginResult:
    username = payload.username.strip().lower()
    if not USERNAME_RE.match(username):
        raise AppError(422, "用户名需为 3-32 位字母、数字或下划线", 42211)

    existing = await db.scalar(
        select(Attendee).where(Attendee.username == username)
    )
    if existing is not None:
        raise AppError(409, "用户名已被注册", 40930)

    nickname = (payload.nickname or "").strip() or payload.username.strip()
    phone = (payload.phone or "").strip() or None
    if phone and not PHONE_RE.match(phone):
        raise AppError(422, "请输入有效的手机号", 42210)

    attendee = Attendee(
        openid=f"web:{uuid4().hex}",
        username=username,
        password_hash=hash_password(payload.password),
        nickname=nickname[:64],
        phone=phone,
    )
    db.add(attendee)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(409, "用户名已被注册", 40930) from exc

    await db.refresh(attendee)
    return _attendee_result(attendee)


async def password_login(
    db: AsyncSession,
    payload: WebPasswordLoginRequest,
    ip: str | None = None,
) -> MpLoginResult:
    username = payload.username.strip().lower()
    key = f"attendee:{ip or 'unknown'}:{username}"
    window_seconds = settings.login_window_minutes * 60

    remaining = seconds_until_allowed(key, window_seconds)
    if remaining > 0:
        minutes = max(1, (remaining + 59) // 60)
        raise AppError(429, f"登录失败次数过多，请 {minutes} 分钟后再试", 42902)

    attendee = await db.scalar(
        select(Attendee).where(Attendee.username == username)
    )
    if (
        attendee is None
        or not attendee.password_hash
        or not verify_password(attendee.password_hash, payload.password)
    ):
        record_failure(
            key,
            settings.login_max_attempts,
            window_seconds,
            settings.login_lock_minutes * 60,
        )
        raise AppError(401, "用户名或密码错误", 40106)

    reset_attempts(key)
    attendee.last_login_at = datetime.now()
    await db.commit()
    await db.refresh(attendee)
    return _attendee_result(attendee)
