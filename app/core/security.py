"""密码、令牌与签名相关的底层安全能力。

设计要点：
1. 密码与静态口令均使用 Argon2id 哈希，数据库中不保存明文；
2. 登录失败时不区分"用户不存在"与"密码错误"，避免账号枚举；
3. 电子票与动态二维码使用 HMAC-SHA256 签名，服务端可离线校验防伪；
4. 所有签名比较使用 ``hmac.compare_digest``，避免时序侧信道。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import Unauthorized

TokenType = Literal["access", "refresh", "ticket"]

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
# 用于账号不存在时执行一次等价耗时的校验
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalization")

QR_SIGNATURE_LENGTH = 32


# --------------------------------------------------------------------------- #
# 密码 / 静态口令
# --------------------------------------------------------------------------- #
def hash_secret(raw: str) -> str:
    return _hasher.hash(raw)


def verify_secret(raw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def burn_password_check() -> None:
    """在账号不存在时调用，使响应耗时与真实校验接近。"""
    verify_secret("dummy-password-for-timing-equalization", _DUMMY_HASH)


def generate_numeric_code(length: int = 6) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode(), right.encode())


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_token(
    *,
    subject: str,
    token_type: Literal["access", "refresh"],
    role: str,
    ttl: timedelta,
) -> tuple[str, str, datetime]:
    """返回 (token, jti, 过期时间)。"""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + ttl
    jti = uuid.uuid4().hex
    payload = {
        "sub": subject,
        "typ": token_type,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": "activityhub",
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise Unauthorized("凭证无效或已过期", code="invalid_token") from exc

    if payload.get("typ") != expected_type:
        raise Unauthorized("凭证类型不正确", code="invalid_token")
    return payload


# --------------------------------------------------------------------------- #
# HMAC 签名载荷（电子票）
# --------------------------------------------------------------------------- #
def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def sign_payload(payload: dict[str, Any]) -> str:
    """生成 ``body.signature`` 形式的防伪串。"""
    secret = get_settings().resolved_ticket_secret
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_signed_payload(token: str) -> dict[str, Any]:
    secret = get_settings().resolved_ticket_secret
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise Unauthorized("票据格式错误", code="invalid_ticket") from exc

    expected = _b64encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not constant_time_equals(signature, expected):
        raise Unauthorized("票据签名校验失败", code="invalid_ticket")

    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise Unauthorized("票据内容损坏", code="invalid_ticket") from exc
    if payload.get("exp") and datetime.fromtimestamp(payload["exp"], UTC) < datetime.now(UTC):
        raise Unauthorized("票据已过期", code="expired_ticket")
    return payload


# --------------------------------------------------------------------------- #
# 动态二维码
# --------------------------------------------------------------------------- #
def qr_signature(nonce: str, event_id: str, expires_at: datetime) -> str:
    secret = get_settings().resolved_ticket_secret
    message = f"{event_id}:{nonce}:{int(expires_at.timestamp())}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:QR_SIGNATURE_LENGTH]


def build_qr_token(nonce: str, event_id: str, expires_at: datetime) -> str:
    return f"{nonce}.{qr_signature(nonce, event_id, expires_at)}"


def verify_qr_token(token: str, nonce: str, event_id: str, expires_at: datetime) -> bool:
    try:
        token_nonce, signature = token.split(".", 1)
    except ValueError:
        return False
    if not constant_time_equals(token_nonce, nonce):
        return False
    return constant_time_equals(signature, qr_signature(nonce, event_id, expires_at))


def derive_display_code(nonce: str) -> str:
    """由 nonce 派生 6 位口令，供大屏同时展示，可手动输入作为扫码兜底。"""
    digest = hmac.new(get_settings().resolved_ticket_secret, f"code:{nonce}".encode(), hashlib.sha256)
    return f"{int(digest.hexdigest(), 16) % 1_000_000:06d}"
