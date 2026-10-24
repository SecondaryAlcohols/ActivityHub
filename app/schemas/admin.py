"""管理端契约：控制台、名单、异常、统计和审计。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AnomalyStatus,
    AnomalyType,
    AttendanceKind,
    AttendanceMethod,
    AttendanceStatus,
    RegistrationStatus,
)
from app.schemas.event import EventCounts


class QrChallengeOut(BaseModel):
    token: str = Field(..., description="动态二维码内容，每 rotation_seconds 秒刷新")
    code: str = Field(..., description="大屏同步展示的 6 位口令")
    issued_at: datetime
    expires_at: datetime
    expires_in: int
    rotation_seconds: int


class ConsoleRecentItem(BaseModel):
    record_id: UUID
    user_name: str
    student_no: str
    kind: AttendanceKind
    occurred_at: datetime
    distance_m: float | None = None
    ip: str | None = None
    face_similarity: float | None = None
    is_manual: bool = False
    status: AttendanceStatus
    anomaly_types: list[AnomalyType] = Field(default_factory=list)


class ConsoleAnomalyItem(BaseModel):
    id: UUID
    type: AnomalyType
    user_name: str | None = None
    student_no: str | None = None
    detail: dict
    detected_at: datetime


class ConsoleResponse(BaseModel):
    event_id: UUID
    title: str
    counts: EventCounts
    recent: list[ConsoleRecentItem]
    anomalies: list[ConsoleAnomalyItem]
    qr: QrChallengeOut | None = None
    server_time: datetime


class RosterState(StrEnum):
    ALL = "all"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    ABSENT = "absent"
    FLAGGED = "flagged"
    PENDING = "pending"


class RosterItem(BaseModel):
    registration_id: UUID
    user_id: UUID
    student_no: str
    name: str
    college: str | None = None
    phone_masked: str | None = None
    status: RegistrationStatus
    applied_at: datetime
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    checkin_methods: list[AttendanceMethod] = Field(default_factory=list)
    checkout_methods: list[AttendanceMethod] = Field(default_factory=list)
    distance_m: float | None = None
    ip: str | None = None
    face_similarity: float | None = None
    is_manual: bool = False
    flagged: bool = False
    anomaly_types: list[AnomalyType] = Field(default_factory=list)
    can_manual_checkin: bool = False


class ApproveResponse(BaseModel):
    registration_id: UUID
    status: RegistrationStatus


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=200)


class ManualCheckinRequest(BaseModel):
    kind: AttendanceKind = AttendanceKind.CHECKIN
    reason: str = Field(..., min_length=2, max_length=255, description="补签原因，写入审计日志")
    occurred_at: datetime | None = Field(None, description="实际发生时间，默认当前时间")


class AnomalyItem(BaseModel):
    id: UUID
    type: AnomalyType
    status: AnomalyStatus
    user_id: UUID | None = None
    user_name: str | None = None
    student_no: str | None = None
    detail: dict
    detected_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class ResolveAnomalyRequest(BaseModel):
    resolution_note: str = Field(..., min_length=2, max_length=255)
    dismiss: bool = Field(False, description="true 表示误报忽略，false 表示已处理")


class EventStatItem(BaseModel):
    event_id: UUID
    title: str
    start_at: datetime
    approved: int
    checked_in: int
    checkin_rate: float


class StatsOverview(BaseModel):
    days: int
    event_count: int
    registration_total: int
    checkin_total: int
    overall_checkin_rate: float
    events: list[EventStatItem]


class AuditLogItem(BaseModel):
    id: int
    actor_name: str | None = None
    actor_role: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict
    created_at: datetime
