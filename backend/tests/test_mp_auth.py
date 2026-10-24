from app.core.config import settings
from tests.conftest import mp_login


async def test_mock_login_creates_attendee_and_me(client):
    headers = await mp_login(client, "alice")

    response = await client.get("/api/mp/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] >= 1
    assert data["nickname"] == ""


async def test_mock_login_reuses_same_attendee(client):
    first = await mp_login(client, "alice")
    second = await mp_login(client, "alice")

    me1 = (await client.get("/api/mp/auth/me", headers=first)).json()["data"]
    me2 = (await client.get("/api/mp/auth/me", headers=second)).json()["data"]
    assert me1["id"] == me2["id"]


async def test_mock_login_requires_prefix(client):
    response = await client.post("/api/mp/auth/login", json={"code": "alice"})
    assert response.status_code == 400
    assert response.json()["code"] == 40002


async def test_mock_login_rejects_invalid_name(client):
    response = await client.post(
        "/api/mp/auth/login", json={"code": "mock:bad name!"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == 40001


async def test_mock_login_disabled_without_wechat_config(client, monkeypatch):
    monkeypatch.setattr(settings, "wechat_mock_login", False)

    response = await client.post("/api/mp/auth/login", json={"code": "mock:alice"})
    assert response.status_code == 503
    assert response.json()["code"] == 50301


async def test_update_profile(client):
    headers = await mp_login(client, "bob")

    response = await client.put(
        "/api/mp/auth/profile",
        json={"nickname": "小明", "avatar_url": "https://example.com/a.png"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["nickname"] == "小明"
    assert data["avatar_url"] == "https://example.com/a.png"


async def test_update_profile_rejects_blank_nickname(client):
    headers = await mp_login(client, "bob")

    response = await client.put(
        "/api/mp/auth/profile", json={"nickname": "   "}, headers=headers
    )
    assert response.status_code == 422


async def test_admin_token_cannot_access_mp_api(client, auth_headers):
    response = await client.get("/api/mp/auth/me", headers=auth_headers)
    assert response.status_code == 401
    assert response.json()["code"] == 40102
