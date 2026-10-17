import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, status_code: int, message: str, code: int | None = None):
        self.status_code = status_code
        self.message = message
        self.code = code if code is not None else status_code * 100


def error_response(status_code: int, message: str, code: int | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code if code is not None else status_code * 100,
            "message": message,
            "data": None,
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.message, exc.code)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    message = "请求参数不合法"
    if errors:
        first = errors[0]
        location = ".".join(
            str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")
        )
        detail = first.get("msg", message)
        message = f"{location}: {detail}" if location else detail
    return error_response(422, message, 42200)


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(exc.status_code, str(exc.detail), exc.status_code * 100)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("未处理的异常: %s %s", request.method, request.url.path)
    return error_response(500, "服务器内部错误", 50000)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
