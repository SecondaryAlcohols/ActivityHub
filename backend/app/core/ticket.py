"""电子票 Token：确定性生成，不落库。

payload = "<registration_id>.<activity_id>"
signature = HMAC-SHA256(TICKET_SECRET, payload) 的前 32 位十六进制
token = base64url(payload) + "." + signature
"""

import base64
import hashlib
import hmac

from app.core.config import settings


def _sign(payload: str) -> str:
    return hmac.new(
        settings.ticket_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


def _b64encode(raw: str) -> str:
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _b64decode(value: str) -> str | None:
    padding = "=" * (-len(value) % 4)
    try:
        raw = base64.urlsafe_b64decode(value + padding)
        return raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def generate_ticket_token(registration_id: int, activity_id: int) -> str:
    payload = f"{registration_id}.{activity_id}"
    return f"{_b64encode(payload)}.{_sign(payload)}"


def verify_ticket_token(token: str) -> tuple[int, int] | None:
    """返回 (registration_id, activity_id)，签名不正确时返回 None。"""
    try:
        encoded, signature = token.split(".", 1)
    except ValueError:
        return None

    payload = _b64decode(encoded)
    if not payload:
        return None
    if not hmac.compare_digest(_sign(payload), signature):
        return None

    parts = payload.split(".")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
