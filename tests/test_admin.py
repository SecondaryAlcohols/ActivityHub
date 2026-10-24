"""管理端控制台、名单、补签、异常、统计与导出测试。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.models.anomaly import Anomaly
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    AttendanceKind,
    AttendanceStatus,
    EventStatus,
    UserRole,
)
from app.models.user import Organization


async def _checkin_record(db_session, event, registration, *, ip: str = "10.20.33.71"):
    record = AttendanceRecord(
        event_id=event.id,
        registration_id=registration.id,
        user_id=registration.user_id,
        kind=AttendanceKind.CHECKIN,
        status=AttendanceStatus.NORMAL,
        occurred_at=datetime.now(UTC),
        verified_methods=["qr"],
        ip=ip,
        distance_m=45.0,
        created_at=datetime.now(UTC),
    )
    db_session.add(record)
    await db_session.commit()
    return record


async def test_console_snapshot(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory(require_qr=True, capacity=10)
    registration = await register_factory(event, student)
    await _checkin_record(db_session, event, registration)

    response = await client.get(
        f"/api/v1/admin/events/{event.id}/console", headers=await auth_headers(client, organizer)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["approved"] == 1
    assert body["counts"]["checked_in"] == 1
    assert body["counts"]["checkin_rate"] == 1.0
    assert body["recent"][0]["user_name"] == student.name
    assert body["qr"]["token"]


async def test_roster_filters_and_search(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    make_user,
    organizer,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory()
    first = await make_user(name="褚梦琪", student_no="2023010201")
    second = await make_user(name="冯子墨", student_no="2023010202")
    third = await make_user(name="王梓萱", student_no="2023010203")

    first_reg = await register_factory(event, first)
    await register_factory(event, second)
    await register_factory(event, third)
    await _checkin_record(db_session, event, first_reg)

    headers = await auth_headers(client, organizer)
    all_items = await client.get(
        f"/api/v1/admin/events/{event.id}/roster", headers=headers
    )
    assert all_items.json()["total"] == 3

    checked_in = await client.get(
        f"/api/v1/admin/events/{event.id}/roster",
        params={"state": "checked_in"},
        headers=headers,
    )
    assert checked_in.json()["total"] == 1
    assert checked_in.json()["items"][0]["name"] == "褚梦琪"
    assert checked_in.json()["items"][0]["checkin_methods"] == ["qr"]

    absent = await client.get(
        f"/api/v1/admin/events/{event.id}/roster",
        params={"state": "absent"},
        headers=headers,
    )
    assert absent.json()["total"] == 2

    searched = await client.get(
        f"/api/v1/admin/events/{event.id}/roster",
        params={"q": "王梓萱"},
        headers=headers,
    )
    assert searched.json()["total"] == 1
    assert searched.json()["items"][0]["phone_masked"].startswith("139")


async def test_manual_checkin_creates_audit_and_anomaly(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    make_user,
    organizer,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory()
    registration = await register_factory(event, student)

    response = await client.post(
        f"/api/v1/admin/registrations/{registration.id}/manual-checkin",
        json={"kind": "checkin", "reason": "现场签到设备故障，人工补签"},
        headers=await auth_headers(client, organizer),
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_manual"] is True
    assert response.json()["note"] == "现场签到设备故障，人工补签"

    anomaly = await db_session.scalar(
        select(Anomaly).where(Anomaly.attendance_record_id == uuid.UUID(response.json()["id"]))
    )
    assert anomaly is not None

    admin = await make_user(role=UserRole.ADMIN, name="管理员", student_no="A9001")
    logs = await client.get(
        "/api/v1/admin/audit-logs",
        params={"action": "attendance.manual_checkin"},
        headers=await auth_headers(client, admin),
    )
    assert logs.status_code == 200
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["actor_name"] == organizer.name


async def test_same_ip_anomaly_is_detected(
    client_factory,
    event_factory,
    register_factory,
    student,
    other_student,
    organizer,
    auth_headers,
) -> None:
    event = await event_factory(require_ip=True, allowed_ip_cidrs=["10.20.0.0/16"])
    await register_factory(event, student)
    await register_factory(event, other_student)

    first_client = client_factory("10.20.33.66")
    second_client = client_factory("10.20.33.66")

    first = await first_client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={},
        headers=await auth_headers(first_client, student),
    )
    assert first.status_code == 201
    assert first.json()["anomalies"] == []

    second = await second_client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={},
        headers=await auth_headers(second_client, other_student),
    )
    assert second.status_code == 201
    assert second.json()["anomalies"][0]["type"] == "same_ip"

    console = await second_client.get(
        f"/api/v1/admin/events/{event.id}/console",
        headers=await auth_headers(second_client, organizer),
    )
    assert console.status_code == 200
    assert len(console.json()["anomalies"]) == 2

    roster = await second_client.get(
        f"/api/v1/admin/events/{event.id}/roster", headers=await auth_headers(second_client, organizer)
    )
    assert all(item["flagged"] for item in roster.json()["items"])

    anomaly_id = console.json()["anomalies"][0]["id"]
    resolved = await second_client.post(
        f"/api/v1/admin/anomalies/{anomaly_id}/resolve",
        json={"resolution_note": "确认为同宿舍共用出口 IP", "dismiss": True},
        headers=await auth_headers(second_client, organizer),
    )
    assert resolved.status_code == 200


async def test_export_csv(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
) -> None:
    event = await event_factory()
    await register_factory(event, student)

    response = await client.get(
        f"/api/v1/admin/events/{event.id}/export.csv", headers=await auth_headers(client, organizer)
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    assert text.startswith("学号,姓名")
    assert student.name in text
    assert "未签到" not in text


async def test_stats_overview(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory()
    registration = await register_factory(event, student)
    await _checkin_record(db_session, event, registration)

    response = await client.get(
        "/api/v1/admin/stats/overview",
        params={"days": 7},
        headers=await auth_headers(client, organizer),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["event_count"] == 1
    assert body["registration_total"] == 1
    assert body["checkin_total"] == 1
    assert body["overall_checkin_rate"] == 1.0
    assert body["events"][0]["title"] == event.title


async def test_cross_organization_access_denied(
    client: httpx.AsyncClient,
    event_factory,
    make_user,
    auth_headers,
    db_session,
) -> None:
    outsider = await make_user(
        role=UserRole.ORGANIZER, name="外部组织者", student_no="T2001"
    )
    org = Organization(
        name="校外合作方",
        contact_name=outsider.name,
        contact_phone=outsider.phone,
        owner_id=outsider.id,
    )
    db_session.add(org)
    await db_session.commit()
    event = await event_factory()

    response = await client.get(
        f"/api/v1/admin/events/{event.id}", headers=await auth_headers(client, outsider)
    )
    assert response.status_code == 403


async def test_publish_requires_attendance_method(
    client: httpx.AsyncClient,
    event_factory,
    organizer,
    auth_headers,
) -> None:
    event = await event_factory(status=EventStatus.DRAFT)
    response = await client.post(
        f"/api/v1/admin/events/{event.id}/publish", headers=await auth_headers(client, organizer)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "attendance_method_required"
