"""用户相关契约。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import RegistrationStatus
from app.schemas.common import ORMModel


class UserBrief(ORMModel):
    id: UUID
    student_no: str
    name: str
    college: str | None = None


class AttendanceProgress(StrEnum):
    PENDING_CHECKIN = "pending_checkin"
    PENDING_CHECKOUT = "pending_checkout"
    COMPLETED = "completed"


class MyAttendanceItem(BaseModel):
    event_id: UUID
    registration_id: UUID
    event_title: str
    cover_color: str
    start_at: datetime
    end_at: datetime
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    duration_minutes: int | None = None
    progress: AttendanceProgress
    requires_checkout: bool


class MyRegistrationItem(BaseModel):
    id: UUID
    event_id: UUID
    event_title: str
    cover_color: str
    location_name: str
    start_at: datetime
    end_at: datetime
    status: RegistrationStatus
    applied_at: datetime
    reject_reason: str | None = None
    ticket_code: str


class FaceStatus(BaseModel):
    enrolled: bool
    provider: str | None = None
    updated_at: datetime | None = None
    note: str = Field(..., description="隐私说明")
