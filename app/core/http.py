"""HTTP 基础设施：请求 ID、访问日志、客户端 IP 解析、安全响应头。"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("activityhub.access")


def get_client_ip(request: Request) -> str:
    """解析客户端 IP。

    默认只信任 TCP 对端地址；只有显式开启 TRUST_PROXY_HEADERS 时才读取
    X-Forwarded-For，避免攻击者伪造 IP 绕过 IP 考勤。
    """
    if get_settings().trusted_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


def _ip_from_scope(scope: Scope) -> str:
    headers = Headers(scope=scope)
    if get_settings().trusted_proxy_headers and (forwarded := headers.get("x-forwarded-for")):
        return forwarded.split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "0.0.0.0"


class RequestContextMiddleware:
    """纯 ASGI 中间件：注入请求 ID、记录访问日志。

    不使用 BaseHTTPMiddleware，避免对 SSE 流式响应产生缓冲副作用。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming_id = Headers(scope=scope).get("x-request-id")
        request_id = incoming_id if incoming_id and len(incoming_id) <= 64 else uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s %s %.1fms ip=%s",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status,
                elapsed_ms,
                _ip_from_scope(scope),
            )
            request_id_var.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
            await send(message)

        await self.app(scope, receive, send_with_headers)
