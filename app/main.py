"""ActivityHub 后端应用入口。

启动：uvicorn app.main:app --reload
文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.http import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.logging import configure_logging
from app.db.session import check_database, dispose_engine

logger = logging.getLogger("activityhub")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "ActivityHub 启动 | env=%s docs=%s", settings.environment, "/docs"
    )
    if await check_database():
        logger.info("数据库连接正常")
    else:
        logger.error("数据库连接失败，请检查 DATABASE_URL")
    yield
    await dispose_engine()
    logger.info("ActivityHub 已停止")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    application = FastAPI(
        title="ActivityHub API",
        description=(
            "校园活动报名与考勤系统后端。\n\n"
            "* 用户端：活动浏览、报名、电子票、叠加式考勤（动态二维码 / 静态口令 / GPS / IP / 人脸）\n"
            "* 管理端：活动配置、签到控制台（SSE 实时流）、名单与补签、异常复核、统计导出\n\n"
            "所有时间字段均为 UTC（ISO 8601），客户端按本地时区展示。"
        ),
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "认证", "description": "注册、登录、令牌刷新与人脸录入"},
            {"name": "活动", "description": "活动浏览、详情与考勤提交"},
            {"name": "报名", "description": "报名、取消、电子票与个人考勤"},
            {"name": "管理端 · 活动", "description": "活动创建、发布、二维码与口令管理"},
            {"name": "管理端 · 考勤与统计", "description": "控制台、实时流、名单、异常、导出"},
        ],
    )

    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @application.get("/health/live", tags=["元信息"], summary="存活探针")
    async def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready", tags=["元信息"], summary="就绪探针（含数据库）")
    async def health_ready(response: Response) -> dict[str, str]:
        database_ok = await check_database()
        if not database_ok:
            response.status_code = 503
        return {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "unavailable",
            "version": application.version,
        }

    return application


app = create_app()
