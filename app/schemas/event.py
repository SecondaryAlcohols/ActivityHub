"""活动与考勤策略契约。"""

from __future__ import annotations

import ipaddress
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import CheckinMode, EventStatus, RegistrationStatus


class EventPhase(StrEnum):
    DRAFT = "draft"
    REGISTERING = "registering"
    REGISTRATION_CLOSED = "registration_closed"
    ONGOING = "ongoing"
    ENDED = "ended"
    CANCELLED = "cancelled"


class AttendanceMethodName(StrEnum):
    STATIC_CODE = "static_code"
    QR = "qr"
    GPS = "gps"
    IP = "ip"
    FACE = "face"


class AttendancePolicy(BaseModel):
    mode: CheckinMode
    methods: list[AttendanceMethodName]
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    checkout_deadline_at: datetime
    requires_checkout: bool
    qr_rotation_seconds: int
    gps_radius_m: int
    gps_max_accuracy_m: int
    face_match_threshold: float
    allowed_ip_cidrs: list[str]
    static_code_valid_from: datetime | None = None
    static_code_valid_to: datetime | None = None


class MyRegistration(BaseModel):
    id: UUID
    status: RegistrationStatus
    ticket_code: str


class MyAttendance(BaseModel):
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    duration_minutes: int | None = None


class EventListItem(BaseModel):
    id: UUID
    title: str
    organization: str
    location_name: str
    cover_color: str
    start_at: datetime
    end_at: datetime
    registration_deadline: datetime
    capacity: int
    registered_count: int = Field(..., description="已占名额（含待审核）")
    remaining: int
    phase: EventPhase
    is_full: bool
    requires_approval: bool
    methods: list[AttendanceMethodName]
    my_registration_status: RegistrationStatus | None = None
    my_attendance_progress: str | None = None


class EventDetail(EventListItem):
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    policy: AttendancePolicy
    host_contact: str | None = None
    my_registration: MyRegistration | None = None
    my_attendance: MyAttendance | None = None
    can_register: bool
    register_blocked_reason: str | None = Field(None, description="不可报名的原因码")
    register_blocked_message: str | None = Field(None, description="面向用户的提示文案")


# --------------------------------------------------------------------------- #
# 管理端：创建 / 编辑
# --------------------------------------------------------------------------- #
class EventCreate(BaseModel):
    org_id: UUID | None = Field(None, description="管理员可为指定主办方创建；组织者默认取本单位")
    title: str = Field(..., min_length=2, max_length=120)
    description: str | None = Field(None, max_length=5000)
    location_name: str = Field(..., min_length=2, max_length=200)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    cover_color: str = Field("#1a73e8", pattern=r"^#[0-9a-fA-F]{6}$")

    start_at: datetime
    end_at: datetime
    registration_deadline: datetime
    capacity: int = Field(..., ge=1, le=100_000)
    requires_approval: bool = False

    checkin_mode: CheckinMode = CheckinMode.CHECKIN_ONLY
    checkin_opens_minutes_before: int = Field(30, ge=0, le=1440)
    checkin_closes_minutes_after: int = Field(60, ge=0, le=1440)
    checkout_deadline_minutes: int = Field(30, ge=0, le=1440)

    require_qr: bool = False
    qr_rotation_seconds: int = Field(10, ge=5, le=300)

    require_static_code: bool = False
    static_code: str | None = Field(None, pattern=r"^\d{6}$", description="6 位数字口令，仅创建/轮换时明文传入")
    static_code_valid_from: datetime | None = None
    static_code_valid_to: datetime | None = None

    require_gps: bool = False
    gps_radius_m: int = Field(200, ge=10, le=5000)
    gps_max_accuracy_m: int = Field(200, ge=10, le=2000)

    require_ip: bool = False
    allowed_ip_cidrs: list[str] = Field(default_factory=list, max_length=20)

    require_face: bool = False
    face_match_threshold: float = Field(0.85, ge=0.5, le=0.99)

    @field_validator("allowed_ip_cidrs")
    @classmethod
    def _validate_cidrs(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            try:
                normalized.append(str(ipaddress.ip_network(item.strip(), strict=False)))
            except ValueError as exc:
                raise ValueError(f"非法网段：{item}") from exc
        return normalized

    @model_validator(mode="after")
    def _validate_event(self) -> EventCreate:
        if self.end_at <= self.start_at:
            raise ValueError("结束时间必须晚于开始时间")
        if self.registration_deadline > self.start_at:
            raise ValueError("报名截止时间不能晚于活动开始时间")
        if self.require_static_code and not self.static_code:
            raise ValueError("启用静态口令时必须设置 6 位口令")
        if (
            self.require_static_code
            and self.static_code_valid_from
            and self.static_code_valid_to
            and self.static_code_valid_to <= self.static_code_valid_from
        ):
            raise ValueError("口令失效时间必须晚于生效时间")
        if self.require_gps and (self.latitude is None or self.longitude is None):
            raise ValueError("启用 GPS 考勤时必须设置活动经纬度")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=5000)
    location_name: str | None = Field(None, min_length=2, max_length=200)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    cover_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")

    start_at: datetime | None = None
    end_at: datetime | None = None
    registration_deadline: datetime | None = None
    capacity: int | None = Field(None, ge=1, le=100_000)
    requires_approval: bool | None = None

    checkin_mode: CheckinMode | None = None
    checkin_opens_minutes_before: int | None = Field(None, ge=0, le=1440)
    checkin_closes_minutes_after: int | None = Field(None, ge=0, le=1440)
    checkout_deadline_minutes: int | None = Field(None, ge=0, le=1440)

    require_qr: bool | None = None
    qr_rotation_seconds: int | None = Field(None, ge=5, le=300)

    require_static_code: bool | None = None
    static_code: str | None = Field(None, pattern=r"^\d{6}$")
    static_code_valid_from: datetime | None = None
    static_code_valid_to: datetime | None = None

    require_gps: bool | None = None
    gps_radius_m: int | None = Field(None, ge=10, le=5000)
    gps_max_accuracy_m: int | None = Field(None, ge=10, le=2000)

    require_ip: bool | None = None
    allowed_ip_cidrs: list[str] | None = Field(None, max_length=20)

    require_face: bool | None = None
    face_match_threshold: float | None = Field(None, ge=0.5, le=0.99)

    @field_validator("allowed_ip_cidrs")
    @classmethod
    def _validate_cidrs(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized: list[str] = []
        for item in value:
            try:
                normalized.append(str(ipaddress.ip_network(item.strip(), strict=False)))
            except ValueError as exc:
                raise ValueError(f"非法网段：{item}") from exc
        return normalized


class EventCounts(BaseModel):
    approved: int
    pending: int
    checked_in: int
    checked_out: int
    absent: int
    anomaly_open: int
    checkin_rate: float


class EventAdminItem(BaseModel):
    id: UUID
    title: str
    org_name: str
    location_name: str
    cover_color: str
    start_at: datetime
    end_at: datetime
    status: EventStatus
    phase: EventPhase
    capacity: int
    approved_count: int
    pending_count: int
    methods: list[AttendanceMethodName]
    checkin_mode: CheckinMode


class EventAdminDetail(EventAdminItem):
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    registration_deadline: datetime
    requires_approval: bool
    policy: AttendancePolicy
    static_code_set: bool
    counts: EventCounts


class PublishResponse(BaseModel):
    id: UUID
    status: EventStatus
    published_at: datetime


class StaticCodeRotateResponse(BaseModel):
    static_code: str = Field(..., description="明文口令，仅本次响应返回，之后不可再获取")
    valid_from: datetime | None = None
    valid_to: datetime | None = None
