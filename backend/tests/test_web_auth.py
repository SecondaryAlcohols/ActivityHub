from app.core.config import settings
from tests.conftest import mp_login


async def web_login(client, nickname="网页用户", phone="13800138000"):
    return await client.post(
        "/api/attendee/auth/login",
        json={"nickname": nickname, "phone": phone},
    )


async def test_web_login_and_me(client):
    response = await web_login(client)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["attendee"]["nickname"] == "网页用户"
    assert data["attendee"]["phone"] == "13800138000"

    token = data["access_token"]
    me = await client.get(
        "/api/attendee/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["phone"] == "13800138000"


async def test_web_login_reuses_phone_and_updates_nickname(client):
    first = await web_login(client, "用户A", "13800138000")
    second = await web_login(client, "用户B", "13800138000")
    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["data"]["attendee"]["id"]
        == second.json()["data"]["attendee"]["id"]
    )
    assert second.json()["data"]["attendee"]["nickname"] == "用户B"


async def test_web_login_rejects_invalid_phone(client):
    response = await web_login(client, phone="12345678901")
    assert response.status_code == 422
    assert response.json()["code"] == 42210


async def test_web_login_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "web_demo_login", False)
    response = await web_login(client)
    assert response.status_code == 403
    assert response.json()["code"] == 40300


async def test_web_token_can_access_attendee_apis(client):
    response = await web_login(client)
    token = response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    registrations = await client.get("/api/mp/registrations", headers=headers)
    assert registrations.status_code == 200
    assert registrations.json()["data"]["total"] == 0

    updated = await client.put(
        "/api/attendee/auth/profile",
        json={"nickname": "新昵称"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["nickname"] == "新昵称"


async def test_mp_and_web_tokens_do_not_mix(client):
    web = await web_login(client)
    web_token = web.json()["data"]["access_token"]
    response = await client.get(
        "/api/admin/activities",
        headers={"Authorization": f"Bearer {web_token}"},
    )
    assert response.status_code == 403

    admin_like = await mp_login(client, "alice")
    response = await client.get("/api/attendee/auth/me", headers=admin_like)
    assert response.status_code == 200
