import http
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ProblemException(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None, type_: str = "about:blank"):
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


def _problem(
    status: int,
    title: str,
    detail: str | None,
    type_: str = "about:blank",
    extra: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"type": type_, "title": title, "status": status}
    if detail:
        body["detail"] = detail
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def _handle_problem(_: Request, exc: ProblemException):
        return _problem(exc.status, exc.title, exc.detail, exc.type_)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException):
        title = http.HTTPStatus(exc.status_code).phrase
        detail = str(exc.detail) if exc.detail is not None else None
        return _problem(exc.status_code, title, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError):
        errors = [
            {k: v for k, v in error.items() if k not in ("input", "ctx")}
            for error in exc.errors()
        ]
        return _problem(
            422,
            "Validation Error",
            "Request validation failed",
            extra={"errors": jsonable_encoder(errors)},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        logger.exception(
            "Unhandled exception processing %s %s", request.method, request.url.path
        )
        return _problem(500, "Internal Server Error", None)
