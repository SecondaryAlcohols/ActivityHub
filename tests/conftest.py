"""测试基础设施：独立测试库、事务清理与常用工厂。"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://activityhub:activityhub@127.0.0.1:5432/activityhub_test"
)
os.environ["SECRET_KEY"] = "test-secret-key-with-enough-length-0123456789"
os.environ["FACE_PROVIDER"] = "stub"
os.environ["LOG_LEVEL"] = "WARNING"
# 测试中大量重复请求同一 IP，放开限流阈值
os.environ["LOGIN_RATE_LIMIT"] = "10000"
os.environ["IP_LOGIN_RATE_LIMIT"] = "10000"
os.environ["REGISTER_RATE_LIMIT"] = "10000"

from sqlalchemy import text  # noqa: E402

from app.core.security import hash_secret  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionFactory, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import (  # noqa: E402
    CheckinMode,
    EventStatus,
    UserRole,
)
from app.models.event import Event  # noqa: E402
from app.models.user import Organization, User  # noqa: E402

TRUNCATE_SQL = text(
    "TRUNCATE attendance_records, anomalies, checkin_attempts, qr_usages, "
    "qr_challenges, registrations, events, face_templates, refresh_tokens, "
    "audit_logs, organizations, users RESTART IDENTITY CASCADE"
)
PASSWORD = "Passw0rd!"


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    async def create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create())


@pytest.fixture(autouse=True)
async def _clean_db(_schema) -> None:
    async with engine.begin() as conn:
        await conn.execute(TRUNCATE_SQL)


@pytest.fixture
async def db_session():
    async with SessionFactory() as session:
        yield session


def build_client(ip: str = "10.20.33.77") -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 51234))
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
async def client():
    async with build_client() as http_client:
        yield http_client


@pytest.fixture
async def client_factory():
    clients: list[httpx.AsyncClient] = []

    def _factory(ip: str = "10.20.33.77") -> httpx.AsyncClient:
        created = build_client(ip)
        clients.append(created)
        return created

    yield _factory

    for created in clients:
        await created.aclose()


async def _create_user(
    session,
    *,
    role: UserRole = UserRole.STUDENT,
    student_no: str | None = None,
    name: str = "测试用户",
    phone: str | None = None,
    password: str = PASSWORD,
) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        student_no=student_no or f"U{suffix}",
        name=name,
        phone=phone or f"139{suffix[:8].rjust(8, '0')}",
        college="计算机学院",
        role=role,
        password_hash=hash_secret(password),
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
def make_user(db_session):
    async def _make(**kwargs) -> User:
        return await _create_user(db_session, **kwargs)

    return _make


@pytest.fixture
async def student(make_user) -> User:
    return await make_user(name="陈雨桐", student_no="2023010118")


@pytest.fixture
async def other_student(make_user) -> User:
    return await make_user(name="李昊然", student_no="2023010119")


@pytest.fixture
async def organizer(db_session, make_user) -> User:
    user = await make_user(role=UserRole.ORGANIZER, name="张同学", student_no="T1001")
    org = Organization(
        name="计算机协会", contact_name=user.name, contact_phone=user.phone, owner_id=user.id
    )
    db_session.add(org)
    await db_session.commit()
    return user


@pytest.fixture
async def organization(db_session, organizer) -> Organization:
    from sqlalchemy import select

    return await db_session.scalar(
        select(Organization).where(Organization.owner_id == organizer.id)
    )


@pytest.fixture
def event_factory(db_session, organization, organizer):
    async def _create(**overrides) -> Event:
        now = datetime.now(UTC)
        defaults = {
            "org_id": organization.id,
            "created_by": organizer.id,
            "title": "前端工程化实践分享会",
            "description": "测试活动",
            "location_name": "图书馆 3F 报告厅",
            "latitude": 31.230416,
            "longitude": 121.473701,
            "cover_color": "#1a73e8",
            "start_at": now - timedelta(minutes=5),
            "end_at": now + timedelta(minutes=55),
            "registration_deadline": now - timedelta(hours=1),
            "capacity": 40,
            "requires_approval": False,
            "status": EventStatus.PUBLISHED,
            "published_at": now,
            "checkin_mode": CheckinMode.CHECKIN_ONLY,
            "require_qr": False,
            "require_static_code": False,
            "require_gps": False,
            "require_ip": False,
            "require_face": False,
        }
        defaults.update(overrides)
        event = Event(**defaults)
        db_session.add(event)
        await db_session.commit()
        return event

    return _create


async def login(client: httpx.AsyncClient, account: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"account": account, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers():
    async def _headers(client: httpx.AsyncClient, user: User) -> dict[str, str]:
        return await login(client, user.student_no)

    return _headers


@pytest.fixture
def register_factory(db_session):
    from app.models.enums import RegistrationStatus
    from app.models.registration import Registration

    async def _register(event, user, status: RegistrationStatus = RegistrationStatus.APPROVED) -> Registration:
        registration = Registration(
            event_id=event.id,
            user_id=user.id,
            status=status,
            ticket_code=uuid.uuid4().hex[:16].upper(),
            applied_at=datetime.now(UTC),
        )
        db_session.add(registration)
        await db_session.commit()
        return registration

    return _register

