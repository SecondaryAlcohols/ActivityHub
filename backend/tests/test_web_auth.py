import pytest


async def register(
    client,
    username="webuser",
    password="password123",
    **extra,
):
    return await client.post(
        "/api/attendee/auth/register",
        json={"username": username, "password": password, **extra},
    )


async def login(client, username="webuser", password="password123"):
    return await client.post(
        "/api/attendee/auth/login",
        json={"username": username, "password": password},
    )


async def test_register_and_me(client):
    response = await register(client, nickname="网页用户", phone="13800138000")
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["attendee"]["username"] == "webuser"
    assert data["attendee"]["nickname"] == "网页用户"
    assert data["attendee"]["phone"] == "13800138000"
    assert "password_hash" not in response.text

    token = data["access_token"]
    me = await client.get(
        "/api/attendee/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "webuser"

    # 用户名大小写不敏感
    relogin = await login(client, username="WebUser")
    assert relogin.status_code == 200
    assert (
        relogin.json()["data"]["attendee"]["id"]
        == data["attendee"]["id"]
    )


async def test_register_defaults_nickname_to_username(client):
    response = await register(client, username="simple_user")
    assert response.status_code == 200
    assert response.json()["data"]["attendee"]["nickname"] == "simple_user"


async def test_register_duplicate_username(client):
    first = await register(client, username="duplicate")
    assert first.status_code == 200

    second = await register(client, username="DUPLICATE")
    assert second.status_code == 409
    assert second.json()["code"] == 40930


async def test_register_validates_input(client):
    short_username = await register(client, username="ab")
    assert short_username.status_code == 422

    short_password = await register(client, username="validuser", password="short")
    assert short_password.status_code == 422

    invalid_phone = await register(
        client, username="phoneuser", phone="12345678901"
    )
    assert invalid_phone.status_code == 422
    assert invalid_phone.json()["code"] == 42210


async def test_login_wrong_password_and_rate_limit(client):
    registered = await register(client, username="ratelimit")
    assert registered.status_code == 200

    for _ in range(5):
        response = await login(client, username="ratelimit", password="wrong-pass")
        assert response.status_code == 401
        assert response.json()["code"] == 40106

    blocked = await login(client, username="ratelimit")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == 42902


async def test_login_unknown_user(client):
    response = await login(client, username="nobody", password="password123")
    assert response.status_code == 401
    assert response.json()["code"] == 40106


async def test_web_token_can_access_attendee_apis(client):
    registered = await register(client, username="tokenuser")
    token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    registrations = await client.get("/api/mp/registrations", headers=headers)
    assert registrations.status_code == 200
    assert registrations.json()["data"]["total"] == 0

    admin = await client.get("/api/admin/activities", headers=headers)
    assert admin.status_code == 403


async def test_profile_update(client):
    registered = await register(client, username="profileuser")
    token = registered.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    updated = await client.put(
        "/api/attendee/auth/profile",
        json={"nickname": "新昵称"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["nickname"] == "新昵称"

    me = await client.get("/api/attendee/auth/me", headers=headers)
    assert me.json()["data"]["nickname"] == "新昵称"
