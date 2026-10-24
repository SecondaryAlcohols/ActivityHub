"""考勤记录：签到与签退各一条，保存完整核验证据。"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.columns import enum_type
from app.models.enums import AttendanceKind, AttendanceStatus
from app.models.event import Event
from app.models.registration import Registration
from app.models.user import User


class AttendanceRecord(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "attendance_records"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="RESTRICT"), nullable=False
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("registrations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    kind: Mapped[AttendanceKind] = mapped_column(enum_type(AttendanceKind, "attendance_kind"), nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        enum_type(AttendanceStatus, "attendance_status"),
        nullable=False,
        default=AttendanceStatus.NORMAL,
    )

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_methods: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(255))

    # ---- 核验证据（用于异常复核）----
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    face_similarity: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    event: Mapped[Event] = relationship(lazy="raise")
    registration: Mapped[Registration] = relationship(lazy="raise")
    user: Mapped[User] = relationship(lazy="raise", foreign_keys=[user_id])
    operator: Mapped[User | None] = relationship(lazy="raise", foreign_keys=[operator_id])

    __table_args__ = (
        UniqueConstraint("registration_id", "kind", name="uq_attendance_records_registration_id_kind"),
        Index("ix_attendance_records_event_id_occurred_at", "event_id", "occurred_at"),
        Index("ix_attendance_records_event_id_kind", "event_id", "kind"),
        Index("ix_attendance_records_event_id_ip", "event_id", "ip"),
    )
