"""字符串加解密（用于人脸特征等敏感字段）。"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailable


@lru_cache
def _fernet() -> Fernet:
    try:
        return Fernet(get_settings().resolved_face_key)
    except (ValueError, TypeError) as exc:
        raise ServiceUnavailable("人脸加密密钥配置无效", code="crypto_key_invalid") from exc


def encrypt_text(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_text(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ServiceUnavailable("人脸特征解密失败，可能是密钥已变更", code="crypto_key_invalid") from exc
