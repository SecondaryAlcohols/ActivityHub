"""活动与考勤策略。

考勤策略直接建模为活动表的列：字段固定、可加数据库约束、便于统计查询，
比塞进 JSONB 更利于长期维护。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.columns import enum_type
from app.models.enums import CheckinMode, EventStatus
from app.models.user import Organization, User


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "events"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # ---- 基本信息 ----
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    cover_color: Mapped[str] = mapped_column(String(20), nullable=False, default="#1a73e8", server_default="#1a73e8")

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registration_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    status: Mapped[EventStatus] = mapped_column(
        enum_type(EventStatus, "event_status"), nullable=False, default=EventStatus.DRAFT
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ---- 考勤模式与时间窗 ----
    checkin_mode: Mapped[CheckinMode] = mapped_column(
        enum_type(CheckinMode, "checkin_mode"), nullable=False, default=CheckinMode.CHECKIN_ONLY
    )
    checkin_opens_minutes_before: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )
    checkin_closes_minutes_after: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    checkout_deadline_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30, server_default="30"
    )

    # ---- 校验方式：可叠加，须逐项通过 ----
    require_qr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    qr_rotation_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")

    require_static_code: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    static_code_hash: Mapped[str | None] = mapped_column(String(255))
    static_code_valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    static_code_valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    require_gps: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    gps_radius_m: Mapped[int] = mapped_column(Integer, nullable=False, default=200, server_default="200")
    gps_max_accuracy_m: Mapped[int] = mapped_column(
        Integer, nullable=False, default=200, server_default="200"
    )

    require_ip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    allowed_ip_cidrs: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    require_face: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    face_match_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.85, server_default="0.85"
    )

    org: Mapped[Organization] = relationship(lazy="raise")
    created_by_user: Mapped[User] = relationship(lazy="raise")

    __table_args__ = (
        Index("ix_events_status_start_at", "status", "start_at"),
        Index("ix_events_org_id_start_at", "org_id", "start_at"),
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint("registration_deadline <= start_at", name="registration_deadline"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
        CheckConstraint("qr_rotation_seconds BETWEEN 5 AND 300", name="qr_rotation_range"),
        CheckConstraint("gps_radius_m BETWEEN 10 AND 5000", name="gps_radius_range"),
        CheckConstraint("gps_max_accuracy_m BETWEEN 10 AND 2000", name="gps_accuracy_range"),
        CheckConstraint("face_match_threshold BETWEEN 0.5 AND 0.99", name="face_threshold_range"),
        CheckConstraint("checkin_opens_minutes_before BETWEEN 0 AND 1440", name="checkin_open_range"),
        CheckConstraint("checkin_closes_minutes_after BETWEEN 0 AND 1440", name="checkin_close_range"),
        CheckConstraint("checkout_deadline_minutes BETWEEN 0 AND 1440", name="checkout_range"),
    )

    # ---- 派生时间窗 ----
    @property
    def checkin_opens_at(self) -> datetime:
        return self.start_at - timedelta(minutes=self.checkin_opens_minutes_before)

    @property
    def checkin_closes_at(self) -> datetime:
        return self.end_at + timedelta(minutes=self.checkin_closes_minutes_after)

    @property
    def checkout_deadline_at(self) -> datetime:
        return self.end_at + timedelta(minutes=self.checkout_deadline_minutes)

    @property
    def requires_checkout(self) -> bool:
        return self.checkin_mode == CheckinMode.CHECKIN_CHECKOUT

    @property
    def methods(self) -> list[str]:
        """按管理端展示顺序返回启用的校验方式。"""
        enabled: list[str] = []
        if self.require_static_code:
            enabled.append("static_code")
        if self.require_qr:
            enabled.append("qr")
        if self.require_gps:
            enabled.append("gps")
        if self.require_ip:
            enabled.append("ip")
        if self.require_face:
            enabled.append("face")
        return enabled
