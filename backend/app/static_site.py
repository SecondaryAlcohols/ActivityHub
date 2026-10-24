"""托管构建后的前端静态文件。

参与者网页版挂在 `/`，管理后台挂在 `/admin`，API 仍是 `/api`。
前端未构建（缺少 dist）时自动跳过，不影响开发模式下的 Vite 代理访问。
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

_NOT_FOUND = {"code": 40400, "message": "资源不存在", "data": None}


def repo_root() -> Path:
    """仓库根目录；打包运行时可显式指定 EVENT_SYSTEM_ROOT。"""
    override = os.getenv("EVENT_SYSTEM_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def mount_frontends(app: FastAPI) -> bool:
    root = repo_root()
    web_dist = root / "web-app" / "dist"
    admin_dist = root / "admin-web" / "dist"
    mounted = False

    if admin_dist.is_dir():
        assets = admin_dist / "assets"
        if assets.is_dir():
            app.mount("/admin/assets", StaticFiles(directory=assets), name="admin-assets")

        @app.get("/admin", include_in_schema=False, response_model=None)
        async def admin_redirect() -> RedirectResponse:
            return RedirectResponse("/admin/")

        @app.get("/admin/{path:path}", include_in_schema=False, response_model=None)
        async def admin_spa(path: str) -> FileResponse | JSONResponse:
            if path.startswith("api/"):
                return JSONResponse(_NOT_FOUND, status_code=404)
            return FileResponse(admin_dist / "index.html")

        mounted = True

    if web_dist.is_dir():
        assets = web_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="web-assets")

        @app.get("/", include_in_schema=False, response_model=None)
        @app.get("/{path:path}", include_in_schema=False, response_model=None)
        async def web_spa(path: str = "") -> FileResponse | JSONResponse:
            if path.startswith("api/"):
                return JSONResponse(_NOT_FOUND, status_code=404)
            candidate = (web_dist / path).resolve()
            if path and web_dist.resolve() in candidate.parents and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(web_dist / "index.html")

        mounted = True

    return mounted
