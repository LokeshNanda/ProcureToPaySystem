from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemException(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None, type_: str = "about:blank"):
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_


def _problem(status: int, title: str, detail: str | None, type_: str = "about:blank") -> JSONResponse:
    body = {"type": type_, "title": title, "status": status}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemException)
    async def _handle_problem(_: Request, exc: ProblemException):
        return _problem(exc.status, exc.title, exc.detail, exc.type_)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException):
        return _problem(exc.status_code, str(exc.detail), None)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError):
        return _problem(422, "Validation Error", str(exc.errors()))
