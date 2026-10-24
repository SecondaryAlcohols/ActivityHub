from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import AppError

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(admin_id: int, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(admin_id),
        "role": role,
        "type": "admin",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_attendee_token(attendee_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.attendee_token_expire_days
    )
    payload = {
        "sub": str(attendee_id),
        "type": "attendee",
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """校验签名与有效期，返回原始载荷（不区分 Token 类型）。"""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "登录已过期，请重新登录", 40101) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "无效的登录凭证", 40102) from exc


def decode_access_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "admin":
        raise AppError(401, "无效的登录凭证", 40102)
    return payload


def decode_attendee_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "attendee":
        raise AppError(401, "无效的登录凭证", 40102)
    return payload
