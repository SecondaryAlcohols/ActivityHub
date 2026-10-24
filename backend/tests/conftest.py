from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.rate_limit import reset_all_attempts
from app.core.security import hash_password
from app.db import get_db
from app.main import create_app
from app.models import AdminUser, Base


@pytest.fixture(autouse=True)
def reset_login_limiter():
    reset_all_attempts()
    yield
    reset_all_attempts()


@pytest.fixture(autouse=True)
def enable_mock_wechat_login(monkeypatch):
    monkeypatch.setattr(settings, "wechat_mock_login", True)
    monkeypatch.setattr(settings, "debug", True)
    yield


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("secret123"),
                display_name="管理员",
                role="super_admin",
                status=True,
            )
        )
        await session.commit()

    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    app = create_app()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest_asyncio.fixture
async def auth_headers(client):
    response = await client.post(
        "/api/admin/auth/login",
        json={"username": "admin", "password": "secret123"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def mp_login(client: AsyncClient, name: str = "alice") -> dict[str, str]:
    response = await client.post("/api/mp/auth/login", json={"code": f"mock:{name}"})
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def activity_payload(**overrides):
    now = datetime.now()
    payload = {
        "title": "技术分享会",
        "summary": "一次内部技术交流",
        "location_name": "报告厅",
        "address": "一号楼 3 层",
        "start_at": (now + timedelta(days=7)).isoformat(),
        "end_at": (now + timedelta(days=7, hours=2)).isoformat(),
        "signup_start_at": (now - timedelta(days=1)).isoformat(),
        "signup_end_at": (now + timedelta(days=6)).isoformat(),
        "capacity": 100,
        "need_review": False,
        "allow_cancel": True,
        "form_schema": [
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
        ],
    }
    payload.update(overrides)
    return payload
