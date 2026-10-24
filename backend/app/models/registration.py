from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntType, TimestampMixin


class Registration(Base, TimestampMixin):
    """报名记录。同一用户同一活动只有一条，取消/拒绝后复用。"""

    __tablename__ = "registration"
    __table_args__ = (
        UniqueConstraint(
            "activity_id", "attendee_id", name="uq_registration_activity_attendee"
        ),
        Index(
            "ix_registration_activity_status_created",
            "activity_id",
            "status",
            "created_at",
        ),
        Index("ix_registration_attendee_created", "attendee_id", "created_at"),
        Index("ix_registration_applicant_phone", "applicant_phone"),
    )

    id: Mapped[int] = mapped_column(BigIntType, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigIntType, ForeignKey("activity.id"), nullable=False
    )
    attendee_id: Mapped[int] = mapped_column(
        BigIntType, ForeignKey("attendee.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    applicant_name: Mapped[str] = mapped_column(String(64), nullable=False)
    applicant_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_by: Mapped[int | None] = mapped_column(
        BigIntType, ForeignKey("admin_user.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
