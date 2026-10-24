"""领域异常与统一错误响应。

对外错误结构固定为：
    {"error": {"code": "...", "message": "...", "details": ...}}
这样客户端只需判断 error.code，不必解析自然语言。
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """所有可预期业务异常的基类。"""

    status_code: int = 400
    code: str = "bad_request"
    message: str = "请求无法处理"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        return {"error": error}


class BadRequest(AppError):
    status_code = 400
    code = "bad_request"
    message = "请求参数不合法"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    message = "登录状态已失效，请重新登录"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    message = "没有权限执行该操作"


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "资源不存在"


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "操作与当前状态冲突"


class Unprocessable(AppError):
    status_code = 422
    code = "unprocessable"
    message = "无法完成该操作"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    message = "操作过于频繁，请稍后再试"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "依赖服务暂不可用"
