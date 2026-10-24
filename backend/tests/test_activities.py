from datetime import datetime, timedelta

from sqlalchemy import update

from app.models.activity import Activity
from tests.conftest import activity_payload


async def create_activity(client, auth_headers, **overrides):
    response = await client.post(
        "/api/admin/activities",
        json=activity_payload(**overrides),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def update_payload(data: dict, **overrides):
    payload = {
        "title": data["title"],
        "cover_url": data["cover_url"],
        "summary": data["summary"],
        "description": data["description"],
        "location_name": data["location_name"],
        "address": data["address"],
        "start_at": data["start_at"],
        "end_at": data["end_at"],
        "signup_start_at": data["signup_start_at"],
        "signup_end_at": data["signup_end_at"],
        "checkin_open_at": data["checkin_open_at"],
        "checkin_close_at": data["checkin_close_at"],
        "capacity": data["capacity"],
        "need_review": data["need_review"],
        "allow_cancel": data["allow_cancel"],
        "cancel_deadline": data["cancel_deadline"],
        "form_schema": data["form_schema"],
        "version": data["version"],
    }
    payload.update(overrides)
    return payload


async def set_taken_count(session_factory, activity_id: int, count: int) -> None:
    async with session_factory() as session:
        await session.execute(
            update(Activity)
            .where(Activity.id == activity_id)
            .values(taken_count=count)
        )
        await session.commit()


async def test_create_and_list_activity(client, auth_headers):
    data = await create_activity(client, auth_headers)
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["taken_count"] == 0
    assert len(data["form_schema"]) == 2

    listed = await client.get("/api/admin/activities", headers=auth_headers)
    assert listed.status_code == 200
    page = listed.json()["data"]
    assert page["total"] == 1
    assert page["items"][0]["title"] == "技术分享会"


async def test_list_filter_by_keyword_and_status(client, auth_headers):
    await create_activity(client, auth_headers, title="读书会")
    await create_activity(client, auth_headers, title="篮球赛")

    filtered = await client.get(
        "/api/admin/activities",
        params={"keyword": "读书"},
        headers=auth_headers,
    )
    assert filtered.json()["data"]["total"] == 1

    by_status = await client.get(
        "/api/admin/activities",
        params={"status": "published"},
        headers=auth_headers,
    )
    assert by_status.json()["data"]["total"] == 0


async def test_update_activity(client, auth_headers):
    data = await create_activity(client, auth_headers)
    response = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, title="技术分享会（改期）"),
        headers=auth_headers,
    )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["title"] == "技术分享会（改期）"
    assert updated["version"] == 2


async def test_stale_version_rejected(client, auth_headers):
    data = await create_activity(client, auth_headers)
    payload = update_payload(data, title="第一次修改")
    first = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=payload,
        headers=auth_headers,
    )
    assert first.status_code == 200

    stale = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=payload,
        headers=auth_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == 40907


async def test_publish_increments_version(client, auth_headers):
    data = await create_activity(client, auth_headers)
    published = await client.post(
        f"/api/admin/activities/{data['id']}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200
    published_data = published.json()["data"]
    assert published_data["status"] == "published"
    assert published_data["version"] == 2
    assert published_data["published_at"] is not None

    stale = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, title="发布后的旧版本编辑"),
        headers=auth_headers,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == 40907

    again = await client.post(
        f"/api/admin/activities/{data['id']}/publish",
        headers=auth_headers,
    )
    assert again.status_code == 409
    assert again.json()["code"] == 40904


async def test_delete_only_draft(client, auth_headers):
    data = await create_activity(client, auth_headers)
    await client.post(
        f"/api/admin/activities/{data['id']}/publish",
        headers=auth_headers,
    )
    rejected = await client.delete(
        f"/api/admin/activities/{data['id']}",
        headers=auth_headers,
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == 40903


async def test_invalid_time_range_rejected(client, auth_headers):
    now = datetime.now()
    response = await client.post(
        "/api/admin/activities",
        json=activity_payload(
            start_at=(now + timedelta(days=7)).isoformat(),
            end_at=(now + timedelta(days=6)).isoformat(),
        ),
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == 42200


async def test_missing_system_field_rejected(client, auth_headers):
    response = await client.post(
        "/api/admin/activities",
        json=activity_payload(
            form_schema=[
                {"key": "name", "label": "姓名", "type": "text", "required": True}
            ]
        ),
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "phone" in response.json()["message"]


async def test_capacity_cannot_be_below_taken_count(
    client, auth_headers, session_factory
):
    data = await create_activity(client, auth_headers)
    await set_taken_count(session_factory, data["id"], 10)

    response = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, capacity=5),
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40908


async def test_form_schema_locked_after_registrations(
    client, auth_headers, session_factory
):
    data = await create_activity(client, auth_headers)
    await set_taken_count(session_factory, data["id"], 1)

    new_schema = data["form_schema"] + [
        {"key": "company", "label": "所在单位", "type": "text", "required": False}
    ]
    response = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, form_schema=new_schema),
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40909


async def test_signup_window_locked_after_registrations(
    client, auth_headers, session_factory
):
    data = await create_activity(client, auth_headers)
    await set_taken_count(session_factory, data["id"], 1)

    new_end = (
        datetime.fromisoformat(data["signup_end_at"]) - timedelta(hours=1)
    ).isoformat()
    response = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, signup_end_at=new_end),
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40916


async def test_update_allowed_when_locked_fields_unchanged(
    client, auth_headers, session_factory
):
    data = await create_activity(client, auth_headers)
    await set_taken_count(session_factory, data["id"], 1)

    response = await client.put(
        f"/api/admin/activities/{data['id']}",
        json=update_payload(data, capacity=50, title="扩大名额"),
        headers=auth_headers,
    )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["capacity"] == 50
    assert updated["title"] == "扩大名额"
    assert updated["version"] == 2
