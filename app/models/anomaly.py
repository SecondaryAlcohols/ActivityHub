"""考勤异常。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.columns import enum_type
from app.models.enums import AnomalyStatus, AnomalyType


class Anomaly(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "anomalies"

    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    attendance_record_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_records.id", ondelete="SET NULL")
    )
    type: Mapped[AnomalyType] = mapped_column(enum_type(AnomalyType, "anomaly_type"), nullable=False)
    status: Mapped[AnomalyStatus] = mapped_column(
        enum_type(AnomalyStatus, "anomaly_status"), nullable=False, default=AnomalyStatus.OPEN
    )
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolution_note: Mapped[str | None] = mapped_column(String(255))

    __table_args__ = (
        Index("ix_anomalies_event_id_status", "event_id", "status"),
        Index("ix_anomalies_event_id_detected_at", "event_id", "detected_at"),
    )
