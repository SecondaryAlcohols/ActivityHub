"""GPS 校验：距离由服务端计算，客户端无法绕过。"""

from __future__ import annotations

from app.services.checkin.base import CheckinError, VerificationContext
from app.utils.geo import haversine_distance


async def verify(ctx: VerificationContext) -> None:
    event = ctx.event
    payload = ctx.payload

    if payload.latitude is None or payload.longitude is None:
        raise CheckinError("gps_required", "请开启定位后重新提交")
    if event.latitude is None or event.longitude is None:
        raise CheckinError("gps_not_configured", "活动未配置考勤坐标，请联系组织者")

    accuracy = payload.accuracy_m or 0.0
    if accuracy > event.gps_max_accuracy_m:
        raise CheckinError(
            "gps_accuracy_low",
            "定位精度不足，请到空旷处重试",
            {"accuracy_m": round(accuracy, 1), "max_accuracy_m": event.gps_max_accuracy_m},
        )

    distance = haversine_distance(event.latitude, event.longitude, payload.latitude, payload.longitude)
    if distance > event.gps_radius_m:
        raise CheckinError(
            "gps_out_of_range",
            f"当前位置距离活动地点约 {distance:.0f} 米，超出 {event.gps_radius_m} 米签到范围",
            {
                "distance_m": round(distance, 1),
                "radius_m": event.gps_radius_m,
                "accuracy_m": round(accuracy, 1),
            },
        )

    ctx.distance_m = round(distance, 1)
    ctx.passed_methods.append("gps")
