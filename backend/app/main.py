from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.activities import router as activities_router
from app.api.admin.auth import router as auth_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.schemas.common import ApiResponse


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth_router, prefix="/api")
    app.include_router(activities_router, prefix="/api")

    @app.get("/api/health", response_model=ApiResponse[dict])
    async def health():
        return ApiResponse(data={"status": "ok"})

    return app


app = create_app()
