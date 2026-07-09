import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.errors import ProblemException
from app.main import create_app

_SECRET_LEAK = "super-secret-internal-detail-should-not-leak"


def _build_app():
    app = create_app()

    @app.get("/boom-problem")
    async def _boom_problem():
        raise ProblemException(
            status=409, title="Conflict", detail="already exists", type_="about:blank"
        )

    class _Payload(BaseModel):
        name: str
        age: int

    @app.post("/needs-body")
    async def _needs_body(payload: _Payload):
        return {"ok": True}

    @app.get("/boom-unexpected")
    async def _boom_unexpected():
        raise RuntimeError(_SECRET_LEAK)

    return app


def _client(app, raise_app_exceptions: bool = True) -> AsyncClient:
    transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_problem_exception_returns_problem_json():
    async with _client(_build_app()) as c:
        resp = await c.get("/boom-problem")
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["type"] == "about:blank"
    assert body["title"] == "Conflict"
    assert body["status"] == 409
    assert body["detail"] == "already exists"


@pytest.mark.asyncio
async def test_validation_error_returns_problem_json():
    async with _client(_build_app()) as c:
        resp = await c.post("/needs-body", json={"name": "x"})  # missing 'age'
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["title"] == "Validation Error"
    assert body["status"] == 422
    assert body["detail"] == "Request validation failed"
    # structured errors attached as an RFC 7807 extension member
    assert isinstance(body["errors"], list)
    assert body["errors"], "expected at least one structured error entry"


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_500_problem_json():
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware re-raises after
    # sending the response, so we must let the transport swallow the re-raise to
    # observe the generic 500 body the client would actually receive.
    async with _client(_build_app(), raise_app_exceptions=False) as c:
        resp = await c.get("/boom-unexpected")
    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["title"] == "Internal Server Error"
    assert body["status"] == 500
    # the original exception message must NOT leak into the response
    assert _SECRET_LEAK not in resp.text
