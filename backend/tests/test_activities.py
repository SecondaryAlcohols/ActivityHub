from datetime import datetime, timedelta

from tests.conftest import activity_payload


async def test_create_and_list_activity(client, auth_headers):
    created = await client.post(
        "/api/admin/activities",
        json=activity_payload(),
        headers=auth_headers,
    )
    assert created.status_code == 200
    data = created.json()["data"]
    assert data["status"] == "draft"
    assert data["taken_count"] == 0
    assert len(data["form_schema"]) == 2

    listed = await client.get("/api/admin/activities", headers=auth_headers)
    assert listed.status_code == 200
    page = listed.json()["data"]
    assert page["total"] == 1
    assert page["items"][0]["title"] == "技术分享会"


async def test_list_filter_by_keyword_and_status(client, auth_headers):
    await client.post(
        "/api/admin/activities",
        json=activity_payload(title="读书会"),
        headers=auth_headers,
    )
    await client.post(
        "/api/admin/activities",
        json=activity_payload(title="篮球赛"),
        headers=auth_headers,
    )

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
    created = await client.post(
        "/api/admin/activities",
        json=activity_payload(),
        headers=auth_headers,
    )
    activity_id = created.json()["data"]["id"]

    updated = await client.put(
        f"/api/admin/activities/{activity_id}",
        json=activity_payload(title="技术分享会（改期）"),
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "技术分享会（改期）"


async def test_publish_flow(client, auth_headers):
    created = await client.post(
        "/api/admin/activities",
        json=activity_payload(),
        headers=auth_headers,
    )
    activity_id = created.json()["data"]["id"]

    published = await client.post(
        f"/api/admin/activities/{activity_id}/publish",
        headers=auth_headers,
    )
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["published_at"] is not None

    again = await client.post(
        f"/api/admin/activities/{activity_id}/publish",
        headers=auth_headers,
    )
    assert again.status_code == 409
    assert again.json()["code"] == 40904


async def test_delete_only_draft(client, auth_headers):
    created = await client.post(
        "/api/admin/activities",
        json=activity_payload(),
        headers=auth_headers,
    )
    activity_id = created.json()["data"]["id"]

    await client.post(
        f"/api/admin/activities/{activity_id}/publish",
        headers=auth_headers,
    )
    rejected = await client.delete(
        f"/api/admin/activities/{activity_id}",
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
