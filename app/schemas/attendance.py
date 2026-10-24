"""用户端考勤契约。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AttendanceKind, AttendanceMethod, AttendanceStatus, RegistrationStatus
from app.schemas.event import AttendancePolicy, MyRegistration


class CheckinRequest(BaseModel):
    qr_token: str | None = Field(None, max_length=128, description="扫码得到的动态令牌")
    qr_code: str | None = Field(None, pattern=r"^\d{6}$", description="手动输入大屏 6 位动态口令")
    static_code: str | None = Field(None, pattern=r"^\d{6}$", description="组织者公布的静态口令")
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    accuracy_m: float | None = Field(None, ge=0, le=100_000, description="定位精度（米）")
    face_image: str | None = Field(None, min_length=8, description="人脸图像 base64，仅内存比对")

    @model_validator(mode="after")
    def _qr_single(self) -> CheckinRequest:
        if self.qr_token and self.qr_code:
            raise ValueError("qr_token 与 qr_code 只能提交一个")
        return self


class AnomalyNotice(BaseModel):
    type: str
    message: str


class AttendanceRecordOut(BaseModel):
    id: UUID
    event_id: UUID
    kind: AttendanceKind
    status: AttendanceStatus
    occurred_at: datetime
    verified_methods: list[AttendanceMethod]
    is_manual: bool
    distance_m: float | None = None
    face_similarity: float | None = None
    ip: str | None = None
    note: str | None = None


class AttendanceState(BaseModel):
    checked_in: bool = False
    checked_out: bool = False
    checkin_at: datetime | None = None
    checkout_at: datetime | None = None
    duration_minutes: int | None = None


class AttendanceResult(BaseModel):
    record: AttendanceRecordOut
    state: AttendanceState
    anomalies: list[AnomalyNotice] = Field(default_factory=list)


class StaticCodeWindow(BaseModel):
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_open: bool = False
    remaining_seconds: int = 0


class AttendanceContext(BaseModel):
    event_id: UUID
    title: str
    location_name: str
    latitude: float | None = None
    longitude: float | None = None
    cover_color: str
    start_at: datetime
    end_at: datetime
    policy: AttendancePolicy
    my_registration: MyRegistration | None = None
    attendance: AttendanceState
    static_code_window: StaticCodeWindow
    server_ip: str
    server_time: datetime
    can_checkin: bool
    can_checkout: bool
    blocked_reason: str | None = Field(None, description="当前不可考勤的原因码")
    blocked_message: str | None = None
    registration_status: RegistrationStatus | None = None
