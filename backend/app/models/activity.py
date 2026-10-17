from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntType, TimestampMixin


class Activity(Base, TimestampMixin):
    __tablename__ = "activity"
    __table_args__ = (Index("ix_activity_status_start", "status", "start_at"),)

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signup_start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signup_end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    checkin_open_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    checkin_close_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    taken_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    need_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    allow_cancel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    cancel_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    form_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_by: Mapped[int] = mapped_column(
        BigIntType, ForeignKey("admin_user.id"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
