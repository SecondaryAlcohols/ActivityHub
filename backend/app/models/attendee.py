from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntType, TimestampMixin


class Attendee(Base, TimestampMixin):
    """小程序用户，按 openid 唯一标识。"""

    __tablename__ = "attendee"

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    unionid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    nickname: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
