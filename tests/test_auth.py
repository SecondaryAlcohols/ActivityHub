"""认证与账号接口测试。"""

from __future__ import annotations

import httpx

from app.core.security import decode_token

from .conftest import PASSWORD


async def test_register_and_login(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "student_no": "2023990001",
            "name": "测试新生",
            "password": PASSWORD,
            "phone": "13700001111",
            "college": "计算机学院",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["student_no"] == "2023990001"
    assert body["role"] == "student"
    assert body["has_face"] is False
    assert "password" not in body

    login_response = await client.post(
        "/api/v1/auth/login", json={"account": "2023990001", "password": PASSWORD}
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 3600

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["name"] == "测试新生"


async def test_login_with_wrong_password_is_rejected(client: httpx.AsyncClient, student) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"account": student.student_no, "password": "WrongPass123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_duplicate_student_no_conflicts(client: httpx.AsyncClient, student) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"student_no": student.student_no, "name": "重复账号", "password": PASSWORD},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_exists"


async def test_refresh_rotates_and_revokes_old_token(client: httpx.AsyncClient, student) -> None:
    tokens = (
        await client.post(
            "/api/v1/auth/login", json={"account": student.student_no, "password": PASSWORD}
        )
    ).json()

    refreshed = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    replay = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "refresh_token_revoked"

    claims = decode_token(new_tokens["refresh_token"], expected_type="refresh")
    assert claims["sub"] == str(student.id)


async def test_logout_revokes_refresh_token(client: httpx.AsyncClient, student) -> None:
    tokens = (
        await client.post(
            "/api/v1/auth/login", json={"account": student.student_no, "password": PASSWORD}
        )
    ).json()

    logout = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert logout.status_code == 200

    after = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert after.status_code == 401


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_face_enrollment(client: httpx.AsyncClient, student, auth_headers) -> None:
    headers = await auth_headers(client, student)
    import base64

    payload = base64.b64encode(b"stub:0.98").decode()
    response = await client.put("/api/v1/auth/face", json={"image": payload}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "stub"

    status = await client.get("/api/v1/auth/face", headers=headers)
    assert status.status_code == 200
    assert status.json()["enrolled"] is True
