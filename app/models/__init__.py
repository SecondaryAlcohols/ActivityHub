"""集中导入所有模型，供 Base.metadata 与 Alembic 自动发现。"""

from app.db.base import Base
from app.models.anomaly import Anomaly
from app.models.attempt import CheckinAttempt
from app.models.attendance import AttendanceRecord
from app.models.audit import AuditLog
from app.models.enums import (
    AnomalyStatus,
    AnomalyType,
    AttendanceKind,
    AttendanceMethod,
    AttendanceStatus,
    AuditAction,
    CheckinMode,
    EventStatus,
    RegistrationStatus,
    UserRole,
)
from app.models.event import Event
from app.models.qr import QrChallenge, QrUsage
from app.models.registration import Registration
from app.models.user import FaceTemplate, Organization, RefreshToken, User

__all__ = [
    "Anomaly",
    "AnomalyStatus",
    "AnomalyType",
    "AttendanceKind",
    "AttendanceMethod",
    "AttendanceRecord",
    "AttendanceStatus",
    "AuditAction",
    "AuditLog",
    "Base",
    "CheckinAttempt",
    "CheckinMode",
    "Event",
    "EventStatus",
    "FaceTemplate",
    "Organization",
    "QrChallenge",
    "QrUsage",
    "RefreshToken",
    "Registration",
    "RegistrationStatus",
    "User",
    "UserRole",
]
