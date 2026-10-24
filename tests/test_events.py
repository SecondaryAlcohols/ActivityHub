"""活动浏览与报名流程测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.core.security import verify_signed_payload
from app.models.enums import RegistrationStatus


def future_event_kwargs(**overrides) -> dict:
    now = datetime.now(UTC)
    values = {
        "start_at": now + timedelta(hours=2),
        "end_at": now + timedelta(hours=4),
        "registration_deadline": now + timedelta(hours=1),
    }
    values.update(overrides)
    return values


async def test_public_event_list_and_detail(
    client: httpx.AsyncClient, event_factory, student
) -> None:
    event = await event_factory(
        title="古籍整理志愿活动",
        capacity=30,
        require_static_code=True,
        static_code_hash="$argon2id$placeholder",
        **future_event_kwargs(),
    )

    listing = await client.get("/api/v1/events", params={"scope": "all"})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["title"] == "古籍整理志愿活动"
    assert item["remaining"] == 30
    assert item["phase"] == "registering"
    assert item["methods"] == ["static_code"]

    detail = await client.get(f"/api/v1/events/{event.id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["organization"] == "计算机协会"
    assert payload["can_register"] is True
    assert payload["policy"]["mode"] == "checkin_only"
    assert "static_code_hash" not in payload


async def test_register_and_duplicate_conflict(
    client: httpx.AsyncClient, event_factory, student, auth_headers
) -> None:
    event = await event_factory(**future_event_kwargs())
    headers = await auth_headers(client, student)

    response = await client.post(f"/api/v1/events/{event.id}/registrations", headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "approved"
    assert len(body["ticket_code"]) == 16

    duplicate = await client.post(f"/api/v1/events/{event.id}/registrations", headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_registered"

    mine = await client.get("/api/v1/me/registrations", headers=headers)
    assert mine.status_code == 200
    assert mine.json()["total"] == 1


async def test_capacity_is_enforced(
    client: httpx.AsyncClient, event_factory, student, other_student, auth_headers
) -> None:
    event = await event_factory(capacity=1, **future_event_kwargs())

    first = await client.post(
        f"/api/v1/events/{event.id}/registrations",
        headers=await auth_headers(client, student),
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/events/{event.id}/registrations",
        headers=await auth_headers(client, other_student),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "event_full"

    detail = await client.get(f"/api/v1/events/{event.id}")
    assert detail.json()["is_full"] is True
    assert detail.json()["remaining"] == 0


async def test_registration_closed_after_deadline(
    client: httpx.AsyncClient, event_factory, student, auth_headers
) -> None:
    now = datetime.now(UTC)
    event = await event_factory(
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=3),
        registration_deadline=now - timedelta(minutes=5),
    )
    response = await client.post(
        f"/api/v1/events/{event.id}/registrations",
        headers=await auth_headers(client, student),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "registration_closed"


async def test_cancel_and_reapply(
    client: httpx.AsyncClient, event_factory, student, auth_headers
) -> None:
    event = await event_factory(**future_event_kwargs())
    headers = await auth_headers(client, student)

    created = (
        await client.post(f"/api/v1/events/{event.id}/registrations", headers=headers)
    ).json()

    cancelled = await client.delete(
        f"/api/v1/registrations/{created['id']}", headers=headers
    )
    assert cancelled.status_code == 200

    detail = await client.get(f"/api/v1/events/{event.id}", headers=headers)
    assert detail.json()["my_registration"]["status"] == "cancelled"

    reapplied = await client.post(f"/api/v1/events/{event.id}/registrations", headers=headers)
    assert reapplied.status_code == 201
    assert reapplied.json()["id"] == created["id"]
    assert reapplied.json()["status"] == "approved"


@pytest.mark.parametrize("requires_approval", [True, False])
async def test_approval_flow(
    client: httpx.AsyncClient,
    event_factory,
    organizer,
    student,
    auth_headers,
    requires_approval: bool,
) -> None:
    event = await event_factory(requires_approval=requires_approval, **future_event_kwargs())
    student_headers = await auth_headers(client, student)

    created = await client.post(
        f"/api/v1/events/{event.id}/registrations", headers=student_headers
    )
    expected = RegistrationStatus.PENDING if requires_approval else RegistrationStatus.APPROVED
    assert created.json()["status"] == expected.value

    if requires_approval:
        roster = await client.get(
            f"/api/v1/admin/events/{event.id}/roster",
            params={"state": "pending"},
            headers=await auth_headers(client, organizer),
        )
        assert roster.status_code == 200
        assert roster.json()["total"] == 1

        approved = await client.post(
            f"/api/v1/admin/registrations/{created.json()['id']}/approve",
            headers=await auth_headers(client, organizer),
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

    mine = await client.get("/api/v1/me/registrations", headers=student_headers)
    assert mine.json()["items"][0]["status"] == "approved"


async def test_ticket_is_signed(
    client: httpx.AsyncClient, event_factory, student, auth_headers
) -> None:
    event = await event_factory(**future_event_kwargs())
    headers = await auth_headers(client, student)
    registration = (
        await client.post(f"/api/v1/events/{event.id}/registrations", headers=headers)
    ).json()

    ticket = await client.get(
        f"/api/v1/me/registrations/{registration['id']}/ticket", headers=headers
    )
    assert ticket.status_code == 200
    body = ticket.json()
    payload = verify_signed_payload(body["ticket_token"])
    assert payload["rid"] == registration["id"]
    assert payload["uid"] == str(student.id)
    assert payload["eid"] == str(event.id)
    assert body["holder_name"] == student.name


async def test_other_user_cannot_cancel(
    client: httpx.AsyncClient, event_factory, student, other_student, auth_headers
) -> None:
    event = await event_factory(**future_event_kwargs())
    registration = (
        await client.post(
            f"/api/v1/events/{event.id}/registrations",
            headers=await auth_headers(client, student),
        )
    ).json()

    response = await client.delete(
        f"/api/v1/registrations/{registration['id']}",
        headers=await auth_headers(client, other_student),
    )
    assert response.status_code == 403
