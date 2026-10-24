import asyncio
from datetime import datetime, timedelta

from app.core.security import hash_password
from app.core.ticket import verify_ticket_token
from app.models.admin_user import AdminUser
from tests.conftest import activity_payload, mp_login


async def create_admin_activity(client, auth_headers, *, publish=True, **overrides):
    response = await client.post(
        "/api/admin/activities",
        json=activity_payload(**overrides),
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    activity = response.json()["data"]

    if publish:
        response = await client.post(
            f"/api/admin/activities/{activity['id']}/publish",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        activity = response.json()["data"]
    return activity


async def signup(client, headers, activity_id, name, phone, **extra):
    answers = {"name": name, "phone": phone, **extra}
    return await client.post(
        f"/api/mp/activities/{activity_id}/registrations",
        json={"answers": answers},
        headers=headers,
    )


async def test_mp_activity_visibility_and_detail(client, auth_headers):
    draft = await create_admin_activity(
        client, auth_headers, publish=False, title="草稿活动"
    )
    published = await create_admin_activity(
        client, auth_headers, title="公开活动"
    )

    listing = await client.get("/api/mp/activities")
    assert listing.status_code == 200
    page = listing.json()["data"]
    assert page["total"] == 1
    assert page["items"][0]["id"] == published["id"]

    detail = await client.get(f"/api/mp/activities/{published['id']}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["title"] == "公开活动"
    assert data["signup_state"]["can_signup"] is True
    assert len(data["form_schema"]) == 2

    hidden = await client.get(f"/api/mp/activities/{draft['id']}")
    assert hidden.status_code == 404


async def test_signup_approved_duplicate_and_mine(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=5, need_review=False
    )
    alice = await mp_login(client, "alice")

    response = await signup(
        client, alice, activity["id"], "Alice", "13800138000"
    )
    assert response.status_code == 200, response.text
    registration = response.json()["data"]
    assert registration["status"] == "approved"

    duplicate = await signup(
        client, alice, activity["id"], "Alice", "13800138000"
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 40910

    detail = await client.get(
        f"/api/mp/activities/{activity['id']}", headers=alice
    )
    data = detail.json()["data"]
    assert data["my_registration"]["status"] == "approved"
    assert data["signup_state"]["can_signup"] is False
    assert data["signup_state"]["reason"] == "already_registered"

    mine = await client.get("/api/mp/registrations", headers=alice)
    assert mine.status_code == 200
    assert mine.json()["data"]["total"] == 1

    stats = await client.get(
        f"/api/admin/activities/{activity['id']}/stats", headers=auth_headers
    )
    stats_data = stats.json()["data"]
    assert stats_data["total"] == 1
    assert stats_data["approved"] == 1
    assert stats_data["remaining"] == 4
    assert stats_data["signup_rate"] == 20

    ticket = await client.get(
        f"/api/mp/registrations/{registration['id']}/ticket", headers=alice
    )
    assert ticket.status_code == 200
    token = ticket.json()["data"]["token"]
    assert verify_ticket_token(token) == (registration["id"], activity["id"])


async def test_signup_pending_review_flow(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=2, need_review=True
    )
    bob = await mp_login(client, "bob")

    response = await signup(client, bob, activity["id"], "Bob", "13900139000")
    assert response.status_code == 200
    registration = response.json()["data"]
    assert registration["status"] == "pending"

    listing = await client.get(
        f"/api/admin/activities/{activity['id']}/registrations",
        params={"status": "pending", "keyword": "Bob"},
        headers=auth_headers,
    )
    assert listing.status_code == 200
    page = listing.json()["data"]
    assert page["total"] == 1
    assert page["items"][0]["id"] == registration["id"]

    detail = await client.get(
        f"/api/admin/registrations/{registration['id']}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["activity"]["id"] == activity["id"]
    assert detail_data["form_schema"]

    review = await client.post(
        f"/api/admin/registrations/{registration['id']}/review",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert review.status_code == 200
    assert review.json()["data"]["status"] == "approved"

    again = await client.post(
        f"/api/admin/registrations/{registration['id']}/review",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert again.status_code == 409
    assert again.json()["code"] == 40917


async def test_capacity_full_and_cancel_release(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=1, need_review=False
    )
    alice = await mp_login(client, "alice")
    bob = await mp_login(client, "bob")

    first = await signup(client, alice, activity["id"], "Alice", "13800138000")
    assert first.status_code == 200

    full = await signup(client, bob, activity["id"], "Bob", "13900139000")
    assert full.status_code == 409
    assert full.json()["code"] == 40911

    cancel = await client.post(
        f"/api/mp/registrations/{first.json()['data']['id']}/cancel",
        headers=alice,
    )
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] == "cancelled"

    refreshed = await client.get(
        f"/api/admin/activities/{activity['id']}", headers=auth_headers
    )
    assert refreshed.json()["data"]["taken_count"] == 0

    second = await signup(client, bob, activity["id"], "Bob", "13900139000")
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "approved"


async def test_reregister_after_cancel_and_reject_reuses_record(
    client, auth_headers
):
    activity = await create_admin_activity(
        client, auth_headers, capacity=2, need_review=False
    )
    alice = await mp_login(client, "alice")

    first = await signup(client, alice, activity["id"], "Alice", "13800138000")
    registration_id = first.json()["data"]["id"]
    await client.post(
        f"/api/mp/registrations/{registration_id}/cancel", headers=alice
    )
    again = await signup(client, alice, activity["id"], "Alice", "13800138000")
    assert again.status_code == 200
    assert again.json()["data"]["id"] == registration_id

    review_activity = await create_admin_activity(
        client, auth_headers, capacity=2, need_review=True
    )
    carol = await mp_login(client, "carol")
    pending = await signup(
        client, carol, review_activity["id"], "Carol", "13700137000"
    )
    pending_id = pending.json()["data"]["id"]

    rejected = await client.post(
        f"/api/admin/registrations/{pending_id}/review",
        json={"action": "reject", "note": "信息不完整"},
        headers=auth_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"

    refreshed = await client.get(
        f"/api/admin/activities/{review_activity['id']}", headers=auth_headers
    )
    assert refreshed.json()["data"]["taken_count"] == 0

    again = await signup(
        client, carol, review_activity["id"], "Carol", "13700137000"
    )
    assert again.status_code == 200
    assert again.json()["data"]["id"] == pending_id
    assert again.json()["data"]["status"] == "pending"


async def test_signup_window_and_status_errors(client, auth_headers):
    now = datetime.now()

    not_started = await create_admin_activity(
        client,
        auth_headers,
        capacity=2,
        signup_start_at=(now + timedelta(days=1)).isoformat(),
        signup_end_at=(now + timedelta(days=2)).isoformat(),
        start_at=(now + timedelta(days=3)).isoformat(),
        end_at=(now + timedelta(days=4)).isoformat(),
    )
    alice = await mp_login(client, "alice")
    response = await signup(client, alice, not_started["id"], "Alice", "13800138000")
    assert response.status_code == 409
    assert response.json()["code"] == 40912

    closed = await create_admin_activity(
        client,
        auth_headers,
        capacity=2,
        signup_start_at=(now - timedelta(days=2)).isoformat(),
        signup_end_at=(now - timedelta(days=1)).isoformat(),
        start_at=(now + timedelta(days=1)).isoformat(),
        end_at=(now + timedelta(days=2)).isoformat(),
    )
    response = await signup(client, alice, closed["id"], "Alice", "13800138000")
    assert response.status_code == 409
    assert response.json()["code"] == 40913

    draft = await create_admin_activity(client, auth_headers, publish=False)
    response = await signup(client, alice, draft["id"], "Alice", "13800138000")
    assert response.status_code == 409
    assert response.json()["code"] == 40914


async def test_form_validation(client, auth_headers):
    schema = [
        {
            "key": "name",
            "label": "姓名",
            "type": "text",
            "required": True,
            "system": True,
        },
        {
            "key": "phone",
            "label": "手机号",
            "type": "phone",
            "required": True,
            "system": True,
        },
        {"key": "company", "label": "单位", "type": "text", "required": False},
        {
            "key": "diet",
            "label": "饮食偏好",
            "type": "select",
            "required": True,
            "options": ["无", "素食"],
        },
        {
            "key": "tags",
            "label": "兴趣",
            "type": "multi_select",
            "required": False,
            "options": ["A", "B"],
        },
        {"key": "age", "label": "年龄", "type": "number", "required": False},
    ]
    activity = await create_admin_activity(
        client, auth_headers, capacity=10, form_schema=schema
    )
    alice = await mp_login(client, "alice")

    missing_name = await client.post(
        f"/api/mp/activities/{activity['id']}/registrations",
        json={"answers": {"phone": "13800138000", "diet": "无"}},
        headers=alice,
    )
    assert missing_name.status_code == 422
    assert missing_name.json()["code"] == 42210
    assert "姓名" in missing_name.json()["message"]

    bad_phone = await signup(
        client, alice, activity["id"], "Alice", "123", diet="无"
    )
    assert bad_phone.status_code == 422
    assert bad_phone.json()["code"] == 42210

    bad_option = await signup(
        client, alice, activity["id"], "Alice", "13800138000", diet="荤食"
    )
    assert bad_option.status_code == 422

    bad_multi = await signup(
        client,
        alice,
        activity["id"],
        "Alice",
        "13800138000",
        diet="无",
        tags=["A", "C"],
    )
    assert bad_multi.status_code == 422

    valid = await signup(
        client,
        alice,
        activity["id"],
        "Alice",
        "13800138000",
        company="研发部",
        diet="素食",
        tags=["A", "B"],
        age="18",
        unknown="should-be-ignored",
    )
    assert valid.status_code == 200, valid.text
    answers = valid.json()["data"]["answers"]
    assert answers["company"] == "研发部"
    assert answers["diet"] == "素食"
    assert answers["tags"] == ["A", "B"]
    assert "unknown" not in answers


async def test_cancel_rules(client, auth_headers):
    no_cancel = await create_admin_activity(
        client, auth_headers, capacity=2, allow_cancel=False
    )
    alice = await mp_login(client, "alice")
    first = await signup(client, alice, no_cancel["id"], "Alice", "13800138000")
    response = await client.post(
        f"/api/mp/registrations/{first.json()['data']['id']}/cancel",
        headers=alice,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40915

    deadline_passed = await create_admin_activity(
        client,
        auth_headers,
        capacity=2,
        cancel_deadline=(datetime.now() - timedelta(hours=1)).isoformat(),
    )
    second = await signup(
        client, alice, deadline_passed["id"], "Alice", "13800138000"
    )
    response = await client.post(
        f"/api/mp/registrations/{second.json()['data']['id']}/cancel",
        headers=alice,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40915

    cancellable = await create_admin_activity(
        client, auth_headers, capacity=2
    )
    third = await signup(
        client, alice, cancellable["id"], "Alice", "13800138000"
    )
    bob = await mp_login(client, "bob")
    response = await client.post(
        f"/api/mp/registrations/{third.json()['data']['id']}/cancel",
        headers=bob,
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40300


async def test_admin_list_filters_detail_and_stats(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=5, need_review=True
    )
    alice = await mp_login(client, "alice")
    bob = await mp_login(client, "bob")
    await signup(client, alice, activity["id"], "Alice", "13800138000")
    await signup(client, bob, activity["id"], "Bob", "13900139000")

    listing = await client.get(
        f"/api/admin/activities/{activity['id']}/registrations",
        headers=auth_headers,
    )
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 2

    filtered = await client.get(
        f"/api/admin/activities/{activity['id']}/registrations",
        params={"keyword": "Alice"},
        headers=auth_headers,
    )
    assert filtered.json()["data"]["total"] == 1
    item = filtered.json()["data"]["items"][0]
    assert item["applicant_name"] == "Alice"

    detail = await client.get(
        f"/api/admin/registrations/{item['id']}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["activity"]["id"] == activity["id"]

    stats_response = await client.get(
        f"/api/admin/activities/{activity['id']}/stats", headers=auth_headers
    )
    stats = stats_response.json()["data"]
    assert stats["total"] == 2
    assert stats["pending"] == 2
    assert stats["remaining"] == 3
    assert stats["signup_rate"] == 40

    draft = await create_admin_activity(client, auth_headers, publish=False)
    response = await client.get(
        f"/api/admin/activities/{draft['id']}/registrations",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40921


async def test_admin_batch_review_and_cancel(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=3, need_review=True
    )
    users = [
        ("alice", "Alice", "13800138000"),
        ("bob", "Bob", "13900139000"),
        ("carol", "Carol", "13700137000"),
    ]
    ids = []
    for username, name, phone in users:
        headers = await mp_login(client, username)
        response = await signup(client, headers, activity["id"], name, phone)
        assert response.status_code == 200
        ids.append(response.json()["data"]["id"])

    approve = await client.post(
        f"/api/admin/registrations/{ids[0]}/review",
        json={"action": "approve"},
        headers=auth_headers,
    )
    assert approve.status_code == 200

    reject = await client.post(
        f"/api/admin/registrations/{ids[1]}/review",
        json={"action": "reject", "note": "名额调整"},
        headers=auth_headers,
    )
    assert reject.status_code == 200
    assert reject.json()["data"]["status"] == "rejected"

    missing_note = await client.post(
        f"/api/admin/registrations/{ids[2]}/review",
        json={"action": "reject"},
        headers=auth_headers,
    )
    assert missing_note.status_code == 422

    batch = await client.post(
        "/api/admin/registrations/batch-review",
        json={"ids": [ids[0], ids[2]], "action": "approve"},
        headers=auth_headers,
    )
    assert batch.status_code == 200
    result = batch.json()["data"]
    assert result["approved"] == 1
    assert result["skipped"] == 1

    stats_response = await client.get(
        f"/api/admin/activities/{activity['id']}/stats", headers=auth_headers
    )
    stats = stats_response.json()["data"]
    assert stats["approved"] == 2
    assert stats["rejected"] == 1
    assert stats["pending"] == 0

    cancel = await client.post(
        f"/api/admin/registrations/{ids[2]}/cancel", headers=auth_headers
    )
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] == "cancelled"

    refreshed = await client.get(
        f"/api/admin/activities/{activity['id']}", headers=auth_headers
    )
    assert refreshed.json()["data"]["taken_count"] == 1
    assert refreshed.json()["data"]["version"] >= 2


async def test_ticket_permissions_and_status(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=2, need_review=False
    )
    alice = await mp_login(client, "alice")
    bob = await mp_login(client, "bob")
    response = await signup(client, alice, activity["id"], "Alice", "13800138000")
    registration_id = response.json()["data"]["id"]

    ticket = await client.get(
        f"/api/mp/registrations/{registration_id}/ticket", headers=alice
    )
    token = ticket.json()["data"]["token"]
    assert verify_ticket_token(token) == (registration_id, activity["id"])
    assert verify_ticket_token(token + "x") is None

    qr = await client.get(f"/api/mp/tickets/{token}.png")
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG")

    invalid_qr = await client.get("/api/mp/tickets/not-a-ticket.png")
    assert invalid_qr.status_code == 404
    assert invalid_qr.json()["code"] == 40403

    forbidden = await client.get(
        f"/api/mp/registrations/{registration_id}/ticket", headers=bob
    )
    assert forbidden.status_code == 403

    await client.post(
        f"/api/mp/registrations/{registration_id}/cancel", headers=alice
    )
    invalid = await client.get(
        f"/api/mp/registrations/{registration_id}/ticket", headers=alice
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == 40915


async def test_staff_cannot_manage_registrations(
    client, auth_headers, session_factory
):
    activity = await create_admin_activity(client, auth_headers, capacity=2)

    async with session_factory() as session:
        session.add(
            AdminUser(
                username="staff2",
                password_hash=hash_password("staff12345"),
                display_name="核销员",
                role="staff",
                status=True,
            )
        )
        await session.commit()

    login = await client.post(
        "/api/admin/auth/login",
        json={"username": "staff2", "password": "staff12345"},
    )
    staff_headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}"
    }
    response = await client.get(
        f"/api/admin/activities/{activity['id']}/registrations",
        headers=staff_headers,
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40300

    alice = await mp_login(client, "alice")
    response = await client.get(
        f"/api/admin/activities/{activity['id']}/registrations",
        headers=alice,
    )
    assert response.status_code == 403


async def test_concurrent_signup_does_not_oversell(client, auth_headers):
    activity = await create_admin_activity(
        client, auth_headers, capacity=3, need_review=False
    )
    users = []
    for index in range(6):
        headers = await mp_login(client, f"user{index}")
        users.append((headers, f"user{index}", f"1390000{index:04d}"))

    async def attempt(headers, name, phone):
        return await signup(client, headers, activity["id"], name, phone)

    responses = await asyncio.gather(
        *(attempt(headers, name, phone) for headers, name, phone in users)
    )
    successes = [response for response in responses if response.status_code == 200]
    conflicts = [response for response in responses if response.status_code == 409]

    assert len(successes) == 3
    assert len(conflicts) == 3
    assert all(response.json()["code"] == 40911 for response in conflicts)

    refreshed = await client.get(
        f"/api/admin/activities/{activity['id']}", headers=auth_headers
    )
    assert refreshed.json()["data"]["taken_count"] == 3
