async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


async def test_login_and_me(client):
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "secret123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["admin"]["username"] == "admin"
    token = body["data"]["access_token"]

    me = await client.get(
        "/api/admin/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["role"] == "super_admin"


async def test_login_with_wrong_password(client):
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == 40103


async def test_protected_endpoint_requires_token(client):
    response = await client.get("/api/admin/activities")
    assert response.status_code == 401
    assert response.json()["code"] == 40100
