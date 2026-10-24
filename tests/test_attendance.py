"""考勤校验测试：二维码、静态口令、GPS、IP 与人脸。"""

from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.core.security import build_qr_token, hash_secret
from app.models.enums import AttendanceKind
from app.models.qr import QrChallenge, QrUsage


async def _student_headers(client, auth_headers, user):
    return await auth_headers(client, user)


async def test_qr_checkin_and_replay_protection(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory(require_qr=True)
    await register_factory(event, student)

    qr = await client.get(
        f"/api/v1/admin/events/{event.id}/qr", headers=await auth_headers(client, organizer)
    )
    assert qr.status_code == 200
    challenge = qr.json()
    assert len(challenge["code"]) == 6
    assert challenge["expires_in"] > 0
    assert "." in challenge["token"]

    headers = await _student_headers(client, auth_headers, student)
    response = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": challenge["token"]},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["record"]["verified_methods"] == ["qr"]
    assert body["state"]["checked_in"] is True

    # 已完成签到后再提交，返回状态冲突
    again = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": challenge["token"]},
        headers=headers,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "already_checked_in"


async def test_qr_expired_and_invalid(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    other_student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory(require_qr=True)
    await register_factory(event, student)
    await register_factory(event, other_student)
    headers = await auth_headers(client, student)

    invalid = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": "deadbeef.invalid"},
        headers=headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "qr_invalid"

    expired_at = datetime.now(UTC) - timedelta(seconds=5)
    nonce = secrets.token_hex(8)
    db_session.add(
        QrChallenge(
            event_id=event.id,
            nonce=nonce,
            code="123456",
            issued_at=expired_at - timedelta(seconds=10),
            expires_at=expired_at,
        )
    )
    await db_session.commit()

    expired = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": build_qr_token(nonce, str(event.id), expired_at)},
        headers=headers,
    )
    assert expired.status_code == 422
    assert expired.json()["error"]["code"] == "qr_expired"

    # 未被使用的 challenge 可由另一用户使用
    live = await client.get(
        f"/api/v1/admin/events/{event.id}/qr", headers=await auth_headers(client, organizer)
    )
    other_headers = await auth_headers(client, other_student)
    ok = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": live.json()["token"]},
        headers=other_headers,
    )
    assert ok.status_code == 201


async def test_qr_already_used_guard(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory(require_qr=True)
    await register_factory(event, student)
    challenge = (
        await client.get(
            f"/api/v1/admin/events/{event.id}/qr", headers=await auth_headers(client, organizer)
        )
    ).json()

    challenge_row = await db_session.scalar(
        select(QrChallenge).where(QrChallenge.event_id == event.id)
    )
    assert challenge_row is not None
    db_session.add(
        QrUsage(
            challenge_id=challenge_row.id,
            user_id=student.id,
            kind=AttendanceKind.CHECKIN,
            used_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    response = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": challenge["token"]},
        headers=await auth_headers(client, student),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "qr_already_used"


async def test_static_code_flow(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    student,
    other_student,
    auth_headers,
    db_session,
) -> None:
    now = datetime.now(UTC)
    event = await event_factory(
        require_static_code=True,
        static_code_hash=hash_secret("826519"),
        static_code_valid_from=now - timedelta(minutes=5),
        static_code_valid_to=now + timedelta(minutes=5),
    )
    await register_factory(event, student)
    await register_factory(event, other_student)
    headers = await auth_headers(client, student)

    wrong = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"static_code": "000000"},
        headers=headers,
    )
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "static_code_invalid"

    ok = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"static_code": "826519"},
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["record"]["verified_methods"] == ["static_code"]

    # 口令窗口已关闭
    closed = await event_factory(
        title="已过期的口令活动",
        require_static_code=True,
        static_code_hash=hash_secret("123456"),
        static_code_valid_from=now - timedelta(minutes=30),
        static_code_valid_to=now - timedelta(minutes=20),
    )
    await register_factory(closed, other_student)
    response = await client.post(
        f"/api/v1/events/{closed.id}/attendance/checkin",
        json={"static_code": "123456"},
        headers=await auth_headers(client, other_student),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "static_code_window_closed"


async def test_gps_range_and_accuracy(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    student,
    auth_headers,
) -> None:
    event = await event_factory(require_gps=True, gps_radius_m=200, gps_max_accuracy_m=200)
    await register_factory(event, student)
    headers = await auth_headers(client, student)

    missing = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin", json={}, headers=headers
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "gps_required"

    far = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"latitude": 31.3000, "longitude": 121.6000, "accuracy_m": 10},
        headers=headers,
    )
    assert far.status_code == 422
    assert far.json()["error"]["code"] == "gps_out_of_range"
    assert far.json()["error"]["details"]["radius_m"] == 200

    low_accuracy = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"latitude": 31.230416, "longitude": 121.473701, "accuracy_m": 500},
        headers=headers,
    )
    assert low_accuracy.status_code == 422
    assert low_accuracy.json()["error"]["code"] == "gps_accuracy_low"

    near = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"latitude": 31.230500, "longitude": 121.473800, "accuracy_m": 12},
        headers=headers,
    )
    assert near.status_code == 201, near.text
    assert near.json()["record"]["distance_m"] < 200


async def test_ip_allowlist(
    client: httpx.AsyncClient,
    client_factory,
    event_factory,
    register_factory,
    student,
    other_student,
    auth_headers,
) -> None:
    event = await event_factory(require_ip=True, allowed_ip_cidrs=["10.20.0.0/16"])
    await register_factory(event, student)
    await register_factory(event, other_student)

    ok = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={},
        headers=await auth_headers(client, student),
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["record"]["verified_methods"] == ["ip"]

    outside = client_factory("8.8.8.8")
    denied = await outside.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={},
        headers=await auth_headers(outside, other_student),
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "ip_not_allowed"


async def test_face_checkin(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    student,
    auth_headers,
) -> None:
    event = await event_factory(require_face=True, face_match_threshold=0.85)
    await register_factory(event, student)
    headers = await auth_headers(client, student)

    not_enrolled = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"face_image": base64.b64encode(b"stub:0.99").decode()},
        headers=headers,
    )
    assert not_enrolled.status_code == 422
    assert not_enrolled.json()["error"]["code"] == "face_not_enrolled"

    enrolled = await client.put(
        "/api/v1/auth/face",
        json={"image": base64.b64encode(b"stub:0.99").decode()},
        headers=headers,
    )
    assert enrolled.status_code == 200

    mismatch = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"face_image": base64.b64encode(b"stub:0.42").decode()},
        headers=headers,
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "face_low_similarity"

    matched = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"face_image": base64.b64encode(b"stub:0.96").decode()},
        headers=headers,
    )
    assert matched.status_code == 201, matched.text
    assert matched.json()["record"]["face_similarity"] == 0.96


async def test_checkin_and_checkout_flow(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    organizer,
    student,
    auth_headers,
) -> None:
    from app.models.enums import CheckinMode

    event = await event_factory(
        require_qr=True, checkin_mode=CheckinMode.CHECKIN_CHECKOUT, checkout_deadline_minutes=30
    )
    await register_factory(event, student)
    headers = await auth_headers(client, student)

    early_checkout = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkout", json={}, headers=headers
    )
    assert early_checkout.status_code == 422
    assert early_checkout.json()["error"]["code"] == "checkout_before_checkin"

    token = (
        await client.get(
            f"/api/v1/admin/events/{event.id}/qr", headers=await auth_headers(client, organizer)
        )
    ).json()["token"]
    checked_in = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={"qr_token": token},
        headers=headers,
    )
    assert checked_in.status_code == 201

    checked_out = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkout",
        json={"qr_token": token},
        headers=headers,
    )
    assert checked_out.status_code == 201, checked_out.text
    state = checked_out.json()["state"]
    assert state["checked_out"] is True
    assert state["duration_minutes"] == 0

    duplicate = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkout",
        json={"qr_token": token},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_checked_out"


async def test_pending_registration_cannot_checkin(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    student,
    auth_headers,
) -> None:
    from app.models.enums import RegistrationStatus

    event = await event_factory()
    await register_factory(event, student, status=RegistrationStatus.PENDING)
    response = await client.post(
        f"/api/v1/events/{event.id}/attendance/checkin",
        json={},
        headers=await auth_headers(client, student),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "pending_approval"


async def test_context_reports_blockers(
    client: httpx.AsyncClient,
    event_factory,
    register_factory,
    student,
    auth_headers,
    db_session,
) -> None:
    event = await event_factory(require_qr=True)
    headers = await auth_headers(client, student)

    not_registered = await client.get(
        f"/api/v1/events/{event.id}/attendance", headers=headers
    )
    assert not_registered.status_code == 200
    assert not_registered.json()["blocked_reason"] == "not_registered"

    await register_factory(event, student)
    context = await client.get(f"/api/v1/events/{event.id}/attendance", headers=headers)
    body = context.json()
    assert body["can_checkin"] is True
    assert body["policy"]["methods"] == ["qr"]
    assert body["my_registration"]["status"] == "approved"
    assert body["server_ip"] == "10.20.33.77"
