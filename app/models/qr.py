"""动态二维码挑战与使用记录。

二维码不是纯离线签名：每次刷新落库一条 challenge，签到成功后写入
qr_usages，从而保证同一二维码对同一用户只能使用一次（防截图重放）。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.columns import enum_type
from app.models.enums import AttendanceKind
from app.models.event import Event


class QrChallenge(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "qr_challenges"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    nonce: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    event: Mapped[Event] = relationship(lazy="raise")

    __table_args__ = (Index("ix_qr_challenges_event_id_expires_at", "event_id", "expires_at"),)


class QrUsage(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "qr_usages"

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("qr_challenges.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[AttendanceKind] = mapped_column(enum_type(AttendanceKind, "attendance_kind"), nullable=False)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "challenge_id", "user_id", "kind", name="uq_qr_usages_challenge_id_user_id_kind"
        ),
    )
