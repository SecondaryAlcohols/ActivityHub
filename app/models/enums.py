"""数据库枚举类型。

数据库内统一存小写值，Python 侧使用可读枚举成员。
"""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    ORGANIZER = "organizer"
    ADMIN = "admin"


class EventStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class CheckinMode(StrEnum):
    CHECKIN_ONLY = "checkin_only"
    CHECKIN_CHECKOUT = "checkin_checkout"


class RegistrationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AttendanceKind(StrEnum):
    CHECKIN = "checkin"
    CHECKOUT = "checkout"


class AttendanceStatus(StrEnum):
    NORMAL = "normal"
    FLAGGED = "flagged"


class AnomalyType(StrEnum):
    SAME_IP = "same_ip"
    FAILED_ATTEMPTS = "failed_attempts"
    MANUAL_OVERRIDE = "manual_override"


class AnomalyStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class AttendanceMethod(StrEnum):
    """记录单次考勤实际通过的校验方式（可叠加）。"""

    QR = "qr"
    STATIC_CODE = "static_code"
    GPS = "gps"
    IP = "ip"
    FACE = "face"
    MANUAL = "manual"


class AuditAction:
    """审计动作常量（存字符串，便于后续扩展无需迁移枚举）。"""

    EVENT_CREATED = "event.created"
    EVENT_UPDATED = "event.updated"
    EVENT_PUBLISHED = "event.published"
    EVENT_CANCELLED = "event.cancelled"
    REGISTRATION_APPROVED = "registration.approved"
    REGISTRATION_REJECTED = "registration.rejected"
    REGISTRATION_CANCELLED = "registration.cancelled"
    MANUAL_CHECKIN = "attendance.manual_checkin"
    ANOMALY_RESOLVED = "anomaly.resolved"
    STATIC_CODE_ROTATED = "event.static_code_rotated"
    FACE_ENROLLED = "user.face_enrolled"
    EXPORT_DOWNLOADED = "event.export_downloaded"
