"""v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import admin_console, admin_events, auth, events, registrations

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(events.router)
api_router.include_router(registrations.router)
api_router.include_router(admin_events.router)
api_router.include_router(admin_console.router)
