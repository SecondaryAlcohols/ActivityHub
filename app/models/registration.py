"""报名记录。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.columns import enum_type
from app.models.enums import RegistrationStatus
from app.models.event import Event
from app.models.user import User


class Registration(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "registrations"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[RegistrationStatus] = mapped_column(
        enum_type(RegistrationStatus, "registration_status"),
        nullable=False,
        default=RegistrationStatus.PENDING,
    )
    # 电子票编号：同一用户重复报名时复用，便于线下核验
    ticket_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reject_reason: Mapped[str | None] = mapped_column(String(200))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event: Mapped[Event] = relationship(lazy="raise")
    user: Mapped[User] = relationship(lazy="raise", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(lazy="raise", foreign_keys=[reviewed_by])

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_registrations_event_id_user_id"),
        Index("ix_registrations_event_id_status", "event_id", "status"),
        Index("ix_registrations_user_id_status", "user_id", "status"),
    )
