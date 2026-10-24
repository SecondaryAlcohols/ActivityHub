"""活动展示层公共逻辑：阶段计算、策略组装、状态判定。"""

from __future__ import annotations

from datetime import datetime

from app.models.enums import AttendanceMethod, EventStatus, RegistrationStatus
from app.models.event import Event
from app.schemas.event import AttendanceMethodName, AttendancePolicy, EventPhase

ACTIVE_REGISTRATION_STATUSES = (RegistrationStatus.PENDING, RegistrationStatus.APPROVED)

METHOD_ORDER = [
    AttendanceMethodName.STATIC_CODE,
    AttendanceMethodName.QR,
    AttendanceMethodName.GPS,
    AttendanceMethodName.IP,
    AttendanceMethodName.FACE,
]


def compute_phase(event: Event, now: datetime) -> EventPhase:
    if event.status == EventStatus.DRAFT:
        return EventPhase.DRAFT
    if event.status == EventStatus.CANCELLED:
        return EventPhase.CANCELLED
    if now < event.start_at:
        return (
            EventPhase.REGISTERING
            if now <= event.registration_deadline
            else EventPhase.REGISTRATION_CLOSED
        )
    if now <= event.end_at:
        return EventPhase.ONGOING
    return EventPhase.ENDED


def methods_of(event: Event) -> list[AttendanceMethodName]:
    mapping = {
        "static_code": AttendanceMethodName.STATIC_CODE,
        "qr": AttendanceMethodName.QR,
        "gps": AttendanceMethodName.GPS,
        "ip": AttendanceMethodName.IP,
        "face": AttendanceMethodName.FACE,
    }
    enabled = {mapping[name] for name in event.methods}
    return [method for method in METHOD_ORDER if method in enabled]


def build_policy(event: Event) -> AttendancePolicy:
    return AttendancePolicy(
        mode=event.checkin_mode,
        methods=methods_of(event),
        checkin_opens_at=event.checkin_opens_at,
        checkin_closes_at=event.checkin_closes_at,
        checkout_deadline_at=event.checkout_deadline_at,
        requires_checkout=event.requires_checkout,
        qr_rotation_seconds=event.qr_rotation_seconds,
        gps_radius_m=event.gps_radius_m,
        gps_max_accuracy_m=event.gps_max_accuracy_m,
        face_match_threshold=event.face_match_threshold,
        allowed_ip_cidrs=event.allowed_ip_cidrs,
        static_code_valid_from=event.static_code_valid_from,
        static_code_valid_to=event.static_code_valid_to,
    )


def verified_methods(values: list[str]) -> list[AttendanceMethod]:
    result: list[AttendanceMethod] = []
    for value in values:
        try:
            result.append(AttendanceMethod(value))
        except ValueError:
            continue
    return result


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 7:
        return None
    return f"{phone[:3]}****{phone[-4:]}"
