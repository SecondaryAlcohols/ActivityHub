"""校验器公共契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import Unprocessable
from app.models.enums import AttendanceKind
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User
from app.schemas.attendance import CheckinRequest


class CheckinError(Unprocessable):
    """考勤校验失败：统一 422 + 稳定错误码，便于客户端精确提示。"""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message, code=code, details=details)


@dataclass(slots=True)
class VerificationContext:
    session: AsyncSession
    event: Event
    registration: Registration
    user: User
    kind: AttendanceKind
    payload: CheckinRequest
    client_ip: str
    user_agent: str | None
    now: datetime
    passed_methods: list[str] = field(default_factory=list)
    distance_m: float | None = None
    face_similarity: float | None = None
