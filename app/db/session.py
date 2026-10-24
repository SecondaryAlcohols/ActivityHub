"""数据库引擎与会话管理。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

_engine_kwargs: dict = {
    "echo": _settings.db_echo,
    "pool_pre_ping": True,
    "connect_args": {"server_settings": {"application_name": "activityhub-api"}},
}
if _settings.environment == "test":
    # 测试用例运行在独立事件循环中，禁用连接池可避免跨 loop 复用连接
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = _settings.db_pool_size
    _engine_kwargs["max_overflow"] = _settings.db_max_overflow
    _engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(_settings.database_url, **_engine_kwargs)

SessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    # 会话级事务由服务层显式提交
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：请求级会话，异常时回滚。"""
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def dispose_engine() -> None:
    await engine.dispose()
