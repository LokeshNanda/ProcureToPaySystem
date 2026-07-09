# Slice 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the self-hostable P2P skeleton — async FastAPI backend with JWT auth, RBAC, append-only audit log, health/ops, ARQ worker, pluggable storage, plus a minimal React shell that logs in end-to-end — so feature slices (ORG → VEN → PO → APR) plug into stable foundations.

**Architecture:** Modular/feature-based FastAPI backend (`app/core` for cross-cutting concerns, `app/modules/*` for features). Async SQLAlchemy 2.x + asyncpg, Alembic async migrations. JWT access/refresh with DB-persisted rotating refresh tokens. Every mutation writes an append-only `audit_log` row via a request-scoped `AuditWriter`. React 18 + Vite + TS + shadcn/Tailwind shell verifies auth through the UI. Everything runs via `docker compose up`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async) + asyncpg, Alembic, PyJWT, argon2-cffi, ARQ, Redis, PostgreSQL 15, pytest + pytest-asyncio + httpx, ruff, mypy. Frontend: Vite, React 18, TypeScript, Tailwind, shadcn/ui, React Router v6, TanStack Query, react-i18next, Vitest + RTL.

## Global Constraints

- Python **3.12+**; Node **20+**.
- All tables get UUID `id` pk, `created_at`, `updated_at` via the shared mixin; timestamps are `TIMESTAMP(timezone=True)`, stored UTC.
- Monetary values (none in Slice 0) would be `NUMERIC(15,2)` + currency — never floats.
- RBAC enforced **server-side on every protected route**; frontend only hides affordances.
- `audit_log` is **append-only** — no update or delete code path may exist for it.
- All error responses are **RFC 7807 problem+json**.
- All frontend user-facing strings go through **react-i18next** from day one (NFR-I18N-01).
- Never log secrets, passwords, tokens, or full bank numbers.
- 12-factor config via env vars; `.env.example` stays in sync with every new variable.
- The 8 roles are fixed: `Admin`, `ProcurementManager`, `Requester`, `Approver`, `APClerk`, `Receiver`, `Auditor`, `Vendor`.
- Requirement IDs (PLT-01, PLT-02, PLT-06, PLT-07, NFR-*) are referenced in commit messages.

---

## File Structure

**Backend**
```
backend/
  pyproject.toml            deps, ruff, mypy, pytest config
  alembic.ini               alembic config (script location = app/alembic)
  Dockerfile
  app/
    __init__.py
    main.py                 app factory: routers, CORS, error handlers, audit middleware
    worker.py               ARQ WorkerSettings + example idempotent task
    seed.py                 idempotent seed: roles + admin
    core/
      config.py             pydantic-settings Settings
      db.py                 async engine, sessionmaker, get_session dep
      logging.py            structured JSON logging setup
      security.py           argon2 hashing + JWT encode/decode
      errors.py             ProblemException + RFC7807 handlers
      rbac.py               role constants + require_roles(...) dependency
      audit.py              AuditWriter + request-scoped actor/IP context + middleware
      storage.py            StorageBackend ABC + LocalStorage + get_storage
      deps.py               get_current_user / get_current_active_user
    models/
      base.py               Base + UUIDAuditMixin
    modules/
      auth/{__init__,router,schemas,service,models}.py
      users/{__init__,router,schemas,service,models}.py
    health/{__init__,router}.py
    alembic/
      env.py                async migration env
      script.py.mako
      versions/0001_initial.py
  tests/
    conftest.py             ephemeral DB, per-test rollback, client, factories
    test_health.py test_security.py test_auth.py test_users.py
    test_rbac.py test_audit.py
```

**Frontend**
```
frontend/
  package.json vite.config.ts tsconfig.json tailwind.config.js postcss.config.js
  index.html
  Dockerfile
  src/
    main.tsx App.tsx
    lib/{api.ts,queryClient.ts}
    i18n/{index.ts,en.json}
    auth/{AuthContext.tsx,ProtectedRoute.tsx}
    pages/{Login.tsx,Home.tsx}
    components/Layout.tsx
    components/ui/…        (shadcn primitives as needed: button, input, card)
  src/__tests__/Login.test.tsx
  vitest.config.ts vitest.setup.ts
```

**Root**
```
docker/docker-compose.yml
Makefile
.env.example
```

---

## Task 1: Backend skeleton — config, logging, app factory, liveness health

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/core/errors.py`, `backend/app/health/__init__.py`, `backend/app/health/router.py`, `backend/app/main.py`
- Test: `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.core.config.Settings` / `settings`; `app.core.errors.ProblemException`, `install_error_handlers(app)`; `app.main.create_app() -> FastAPI`; `GET /health` → `{"status":"ok"}`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "openp2p-backend"
version = "0.0.1"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "sqlalchemy[asyncio]>=2.0.30",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "pydantic>=2.7",
  "pydantic-settings>=2.3",
  "pyjwt>=2.8",
  "argon2-cffi>=23.1",
  "arq>=0.26",
  "redis>=5.0",
  "python-multipart>=0.0.9",
  "email-validator>=2.1",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27", "ruff>=0.5", "mypy>=1.10"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
plugins = ["pydantic.mypy"]
ignore_missing_imports = true
```

- [ ] **Step 2: Write the failing test** — `backend/tests/test_health.py`

```python
import pytest


@pytest.mark.asyncio
async def test_health_liveness(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 3: Minimal `conftest.py`** (client fixture only; DB fixtures added in Task 3)

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

Also create empty `backend/tests/__init__.py`.

- [ ] **Step 4: `config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://openp2p:openp2p@localhost:5432/openp2p"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    secret_encryption_key: str = ""
    storage_backend: str = "local"
    storage_local_root: str = "./storage_data"
    frontend_origin: str = "http://localhost:5173"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin"


settings = Settings()
```

- [ ] **Step 5: `logging.py`**

```python
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
```

- [ ] **Step 6: `errors.py`** (RFC 7807)

```python
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
```

- [ ] **Step 7: `health/router.py`**

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8: `main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging
from app.health.router import router as health_router


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="OpenP2P", version="0.0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
```

- [ ] **Step 9: Run tests**

Run: `cd backend && pip install -e ".[dev]" && pytest tests/test_health.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(PLT-07): backend skeleton with config, logging, RFC7807 errors, liveness health"
```

---

## Task 2: Security core — password hashing & JWT (no DB)

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str) -> str`
  - `verify_password(hashed: str, password: str) -> bool`
  - `create_access_token(*, sub: str, roles: list[str], jti: str) -> str`
  - `create_refresh_token(*, sub: str, jti: str) -> str`
  - `decode_token(token: str) -> dict` (raises `ProblemException(401,...)` on invalid/expired)

- [ ] **Step 1: Write the failing test**

```python
import pytest

from app.core.errors import ProblemException
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password(h, "s3cret") is True
    assert verify_password(h, "wrong") is False


def test_access_token_round_trip():
    token = create_access_token(sub="user-1", roles=["Admin"], jti="j1")
    claims = decode_token(token)
    assert claims["sub"] == "user-1"
    assert claims["roles"] == ["Admin"]
    assert claims["type"] == "access"
    assert claims["jti"] == "j1"


def test_decode_rejects_garbage():
    with pytest.raises(ProblemException):
        decode_token("not-a-jwt")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: FAIL (module `app.core.security` not found).

- [ ] **Step 3: Implement `security.py`**

```python
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings
from app.core.errors import ProblemException

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except Argon2Error:
        return False


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(*, sub: str, roles: list[str], jti: str) -> str:
    exp = _now() + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {"sub": sub, "roles": roles, "jti": jti, "type": "access", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, sub: str, jti: str) -> str:
    exp = _now() + timedelta(days=settings.refresh_token_ttl_days)
    payload = {"sub": sub, "jti": jti, "type": "refresh", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise ProblemException(401, "Token Expired", "The token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise ProblemException(401, "Invalid Token", "The token is invalid.") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_security.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat(PLT-01): argon2 password hashing and JWT access/refresh token helpers"
```

---

## Task 3: Database layer, base model, and test DB harness

**Files:**
- Create: `backend/app/core/db.py`, `backend/app/models/__init__.py`, `backend/app/models/base.py`
- Modify: `backend/tests/conftest.py` (add DB fixtures)
- Test: reuse `test_health.py` (still passes); add `backend/tests/test_db.py`

**Interfaces:**
- Produces:
  - `app.core.db.engine`, `app.core.db.SessionLocal`, `async def get_session() -> AsyncIterator[AsyncSession]`
  - `app.models.base.Base` (DeclarativeBase), `app.models.base.UUIDAuditMixin`
  - conftest fixtures: `db_session` (an `AsyncSession` rolled back per test), `client` (now overrides `get_session` to use `db_session`)

- [ ] **Step 1: `models/base.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UUIDAuditMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: `core/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Extend `conftest.py` with a rollback-per-test DB harness**

Requires a running Postgres. Uses a dedicated test database URL from `TEST_DATABASE_URL` (defaults to the app DB name suffixed `_test`). Creates all tables once per session, wraps each test in an outer transaction bound to a single connection, and rolls back.

```python
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_session
from app.main import create_app
from app.models.base import Base
# Import all model modules so Base.metadata is fully populated:
import app.modules.users.models  # noqa: F401  (added in Task 4)
import app.modules.auth.models  # noqa: F401   (added in Task 7)
import app.core.audit  # noqa: F401           (AuditLog model, added in Task 6)

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://openp2p:openp2p@localhost:5432/openp2p_test",
)


@pytest_asyncio.fixture(scope="session")
async def _engine():
    eng = create_async_engine(TEST_DB_URL, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(_engine):
    connection = await _engine.connect()
    trans = await connection.begin()
    maker = async_sessionmaker(bind=connection, expire_on_commit=False, class_=AsyncSession)
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

> Note: the three `import ...  # noqa` lines reference modules created in later tasks. When implementing Task 3 alone, include only imports for modules that already exist and add the rest as those tasks land. The comment markers show the end state.

- [ ] **Step 4: `test_db.py`**

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_session_executes(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
```

- [ ] **Step 5: Run tests**

Run: `cd backend && createdb openp2p_test 2>/dev/null; pytest tests/test_db.py tests/test_health.py -v`
Expected: PASS (Postgres must be reachable; see Task 12 for compose).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/db.py backend/app/models backend/tests/conftest.py backend/tests/test_db.py
git commit -m "feat: async SQLAlchemy engine, base model mixin, and rollback-per-test DB harness"
```

---

## Task 4: User, Role, user_roles models + users service (hash on create)

**Files:**
- Create: `backend/app/modules/__init__.py`, `backend/app/modules/users/__init__.py`, `backend/app/modules/users/models.py`, `backend/app/modules/users/service.py`
- Test: `backend/tests/test_users.py` (service-level tests here; HTTP tests in Task 9)

**Interfaces:**
- Produces:
  - Models `User` (id, email unique lower, password_hash, full_name, is_active, last_login_at, `roles` relationship), `Role` (id, name unique, description), `user_roles` table.
  - `app.modules.users.service`:
    - `async def create_user(db, *, email, full_name, password, role_names) -> User`
    - `async def get_by_email(db, email) -> User | None`
    - `async def set_roles(db, user, role_names) -> User`
    - `async def deactivate(db, user) -> User`
    - `async def get_or_create_role(db, name, description="") -> Role`

- [ ] **Step 1: Failing test**

```python
import pytest

from app.modules.users import service


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_lowercases_email(db_session):
    user = await service.create_user(
        db_session, email="Alice@Example.com", full_name="Alice",
        password="pw123456", role_names=["Requester"],
    )
    assert user.email == "alice@example.com"
    assert user.password_hash != "pw123456"
    assert {r.name for r in user.roles} == {"Requester"}
    assert user.is_active is True


@pytest.mark.asyncio
async def test_set_roles_replaces_roles(db_session):
    user = await service.create_user(
        db_session, email="bob@example.com", full_name="Bob",
        password="pw123456", role_names=["Requester"],
    )
    await service.set_roles(db_session, user, ["Approver", "Receiver"])
    assert {r.name for r in user.roles} == {"Approver", "Receiver"}
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_users.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: `models.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Table, Column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDAuditMixin

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(UUIDAuditMixin, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class User(UUIDAuditMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")
```

- [ ] **Step 4: `service.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.models import Role, User


async def get_or_create_role(db: AsyncSession, name: str, description: str = "") -> Role:
    role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
    if role is None:
        role = Role(name=name, description=description)
        db.add(role)
        await db.flush()
    return role


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return (
        await db.execute(select(User).where(User.email == email.lower()))
    ).scalar_one_or_none()


async def create_user(
    db: AsyncSession, *, email: str, full_name: str, password: str, role_names: list[str]
) -> User:
    roles = [await get_or_create_role(db, n) for n in role_names]
    user = User(
        email=email.lower(),
        full_name=full_name,
        password_hash=hash_password(password),
        roles=roles,
    )
    db.add(user)
    await db.flush()
    return user


async def set_roles(db: AsyncSession, user: User, role_names: list[str]) -> User:
    user.roles = [await get_or_create_role(db, n) for n in role_names]
    await db.flush()
    return user


async def deactivate(db: AsyncSession, user: User) -> User:
    user.is_active = False
    await db.flush()
    return user
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_users.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules backend/tests/test_users.py
git commit -m "feat(PLT-02): user/role models and users service with password hashing"
```

---

## Task 5: Role constants, current-user deps, and require_roles RBAC dependency

**Files:**
- Create: `backend/app/core/rbac.py`, `backend/app/core/deps.py`
- Test: `backend/tests/test_rbac.py`

**Interfaces:**
- Consumes: `decode_token` (Task 2), `get_session` (Task 3), `User`/service `get_by_email` (Task 4).
- Produces:
  - `app.core.rbac.Roles` (constants: `ADMIN`, `PROCUREMENT_MANAGER`, `REQUESTER`, `APPROVER`, `AP_CLERK`, `RECEIVER`, `AUDITOR`, `VENDOR`) and `ALL_ROLES: list[str]`.
  - `app.core.rbac.require_roles(*roles: str)` → FastAPI dependency returning the current `User`, raising `ProblemException(403,...)` if none match.
  - `app.core.deps.get_current_user(...)` → resolves bearer token → active `User`; `get_current_active_user` alias.

- [ ] **Step 1: Failing test** (uses a tiny throwaway app that mounts a protected route)

```python
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.core.rbac import Roles, require_roles
from app.core.security import create_access_token
from app.main import create_app
from app.modules.users import service


@pytest_asyncio.fixture
async def rbac_client(db_session):
    app = create_app()

    @app.get("/admin-only")
    async def admin_only(user=require_roles(Roles.ADMIN)):
        return {"user_id": str(user.id)}

    app.dependency_overrides[get_session] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, db_session


@pytest.mark.asyncio
async def test_require_roles_allows_matching_role(rbac_client):
    client, db = rbac_client
    user = await service.create_user(
        db, email="admin@x.com", full_name="A", password="pw123456", role_names=[Roles.ADMIN]
    )
    token = create_access_token(sub=str(user.id), roles=[Roles.ADMIN], jti="j")
    resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_require_roles_forbids_other_role(rbac_client):
    client, db = rbac_client
    user = await service.create_user(
        db, email="req@x.com", full_name="R", password="pw123456", role_names=[Roles.REQUESTER]
    )
    token = create_access_token(sub=str(user.id), roles=[Roles.REQUESTER], jti="j")
    resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_missing_token_is_401(rbac_client):
    client, _ = rbac_client
    resp = await client.get("/admin-only")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_rbac.py -v`
Expected: FAIL (modules not found).

- [ ] **Step 3: `rbac.py`**

```python
from fastapi import Depends

from app.core.deps import get_current_active_user
from app.core.errors import ProblemException
from app.modules.users.models import User


class Roles:
    ADMIN = "Admin"
    PROCUREMENT_MANAGER = "ProcurementManager"
    REQUESTER = "Requester"
    APPROVER = "Approver"
    AP_CLERK = "APClerk"
    RECEIVER = "Receiver"
    AUDITOR = "Auditor"
    VENDOR = "Vendor"


ALL_ROLES = [
    Roles.ADMIN, Roles.PROCUREMENT_MANAGER, Roles.REQUESTER, Roles.APPROVER,
    Roles.AP_CLERK, Roles.RECEIVER, Roles.AUDITOR, Roles.VENDOR,
]


def require_roles(*required: str):
    async def _dep(user: User = Depends(get_current_active_user)) -> User:
        held = {r.name for r in user.roles}
        if not held.intersection(required):
            raise ProblemException(403, "Forbidden", "You lack the required role.")
        return user

    return Depends(_dep)
```

- [ ] **Step 4: `deps.py`**

```python
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.security import decode_token
from app.modules.users.models import User


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ProblemException(401, "Not Authenticated", "Missing bearer token.")
    return header.removeprefix("Bearer ").strip()


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_session)
) -> User:
    claims = decode_token(_bearer(request))
    if claims.get("type") != "access":
        raise ProblemException(401, "Invalid Token", "Not an access token.")
    user = await db.get(User, __import__("uuid").UUID(claims["sub"]))
    if user is None:
        raise ProblemException(401, "Invalid Token", "User not found.")
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise ProblemException(403, "Inactive User", "This account is deactivated.")
    return user
```

> Replace the inline `__import__("uuid").UUID(...)` with a top-level `import uuid` and `uuid.UUID(claims["sub"])` when implementing — shown inline only to keep the import list obvious.

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_rbac.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/rbac.py backend/app/core/deps.py backend/tests/test_rbac.py
git commit -m "feat(NFR-SEC-01): current-user dependency and require_roles RBAC guard"
```

---

## Task 6: Append-only audit log — model, writer, request context middleware

**Files:**
- Create: `backend/app/core/audit.py`
- Modify: `backend/app/main.py` (register middleware)
- Test: `backend/tests/test_audit.py`

**Interfaces:**
- Produces:
  - Model `AuditLog` (table `audit_log`): `actor_id` (nullable), `action`, `object_type`, `object_id` (nullable str), `before` (JSONB), `after` (JSONB), `ip`, `at` (timestamptz).
  - `set_audit_context(actor_id: str | None, ip: str | None)` / `get_audit_context()` (contextvars).
  - `class AuditWriter` with `async def record(self, db, *, action, object_type, object_id=None, before=None, after=None) -> AuditLog` — pulls actor/ip from context.
  - `AuditMiddleware` that sets the request IP into context (actor set later by auth deps).

- [ ] **Step 1: Failing test**

```python
import pytest
from sqlalchemy import select

from app.core.audit import AuditLog, AuditWriter, set_audit_context


@pytest.mark.asyncio
async def test_audit_writer_records_entry(db_session):
    set_audit_context(actor_id="actor-1", ip="1.2.3.4")
    writer = AuditWriter()
    await writer.record(
        db_session, action="user.create", object_type="user",
        object_id="u1", before=None, after={"email": "x@y.com"},
    )
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "user.create"
    assert rows[0].actor_id == "actor-1"
    assert rows[0].ip == "1.2.3.4"
    assert rows[0].after == {"email": "x@y.com"}
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_audit.py -v`
Expected: FAIL.

- [ ] **Step 3: `audit.py`**

```python
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.models.base import Base, UUIDAuditMixin

_actor: ContextVar[str | None] = ContextVar("audit_actor", default=None)
_ip: ContextVar[str | None] = ContextVar("audit_ip", default=None)


def set_audit_context(actor_id: str | None, ip: str | None) -> None:
    _actor.set(actor_id)
    _ip.set(ip)


def set_audit_actor(actor_id: str | None) -> None:
    _actor.set(actor_id)


def get_audit_context() -> tuple[str | None, str | None]:
    return _actor.get(), _ip.get()


class AuditLog(UUIDAuditMixin, Base):
    __tablename__ = "audit_log"
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditWriter:
    async def record(
        self,
        db: AsyncSession,
        *,
        action: str,
        object_type: str,
        object_id: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLog:
        actor_id, ip = get_audit_context()
        entry = AuditLog(
            actor_id=actor_id, action=action, object_type=object_type,
            object_id=object_id, before=before, after=after, ip=ip,
            at=datetime.now(tz=timezone.utc),
        )
        db.add(entry)
        await db.flush()
        return entry


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else None
        set_audit_context(actor_id=None, ip=client_ip)
        return await call_next(request)
```

- [ ] **Step 4: Register middleware in `main.py`**

Add import `from app.core.audit import AuditMiddleware` and, inside `create_app` after CORS: `app.add_middleware(AuditMiddleware)`.

- [ ] **Step 5: Wire actor into context from auth dep**

In `app/core/deps.py`, at the end of `get_current_user`, before returning, call `set_audit_actor(str(user.id))` (import from `app.core.audit`). This associates the authenticated actor with subsequent audit writes in the same request.

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_audit.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/audit.py backend/app/main.py backend/app/core/deps.py backend/tests/test_audit.py
git commit -m "feat(PLT-06): append-only audit log model, writer, and request-context middleware"
```

---

## Task 7: Auth module — login, refresh (rotation), logout

**Files:**
- Create: `backend/app/modules/auth/__init__.py`, `backend/app/modules/auth/models.py`, `backend/app/modules/auth/schemas.py`, `backend/app/modules/auth/service.py`, `backend/app/modules/auth/router.py`
- Modify: `backend/app/main.py` (include auth router)
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `security` helpers (Task 2), `users.service.get_by_email` (Task 4), `AuditWriter` (Task 6), `get_session` (Task 3).
- Produces:
  - Models `RefreshToken` (user_id, jti unique, expires_at, revoked_at) and `PasswordResetToken` (added Task 8).
  - Endpoints: `POST /auth/login` → `{access_token, refresh_token, token_type}`; `POST /auth/refresh` (rotates); `POST /auth/logout` (revokes).
  - `service.authenticate(db, email, password) -> User | None`; `service.issue_tokens(db, user) -> TokenPair`; `service.rotate(db, refresh_token) -> TokenPair`; `service.revoke(db, refresh_token) -> None`.

- [ ] **Step 1: Failing test**

```python
import pytest

from app.core.rbac import Roles
from app.modules.users import service as users_service


@pytest.mark.asyncio
async def test_login_success_and_me_flow(client, db_session):
    await users_service.create_user(
        db_session, email="admin@x.com", full_name="A",
        password="pw123456", role_names=[Roles.ADMIN],
    )
    resp = await client.post("/auth/login", json={"email": "admin@x.com", "password": "pw123456"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_401(client, db_session):
    await users_service.create_user(
        db_session, email="admin@x.com", full_name="A",
        password="pw123456", role_names=[Roles.ADMIN],
    )
    resp = await client.post("/auth/login", json={"email": "admin@x.com", "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_and_old_token_rejected(client, db_session):
    await users_service.create_user(
        db_session, email="a@x.com", full_name="A", password="pw123456", role_names=[Roles.ADMIN]
    )
    login = (await client.post("/auth/login", json={"email": "a@x.com", "password": "pw123456"})).json()
    old_refresh = login["refresh_token"]
    r1 = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    r2 = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401  # old token was revoked on rotation
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL.

- [ ] **Step 3: `models.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDAuditMixin


class RefreshToken(UUIDAuditMixin, Base):
    __tablename__ = "refresh_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: `schemas.py`**

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
```

- [ ] **Step 5: `service.py`**

```python
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import TokenPair
from app.modules.users.models import User
from app.modules.users.service import get_by_email


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def issue_tokens(db: AsyncSession, user: User) -> TokenPair:
    jti = uuid.uuid4().hex
    db.add(RefreshToken(
        user_id=user.id, jti=jti,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    ))
    await db.flush()
    roles = [r.name for r in user.roles]
    return TokenPair(
        access_token=create_access_token(sub=str(user.id), roles=roles, jti=uuid.uuid4().hex),
        refresh_token=create_refresh_token(sub=str(user.id), jti=jti),
    )


async def _valid_refresh_row(db: AsyncSession, token: str) -> tuple[User, RefreshToken]:
    from app.core.errors import ProblemException
    claims = decode_token(token)
    if claims.get("type") != "refresh":
        raise ProblemException(401, "Invalid Token", "Not a refresh token.")
    row = (await db.execute(select(RefreshToken).where(RefreshToken.jti == claims["jti"]))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise ProblemException(401, "Invalid Token", "Refresh token revoked or unknown.")
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise ProblemException(401, "Invalid Token", "User not found or inactive.")
    return user, row


async def rotate(db: AsyncSession, token: str) -> TokenPair:
    user, row = await _valid_refresh_row(db, token)
    row.revoked_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return await issue_tokens(db, user)


async def revoke(db: AsyncSession, token: str) -> None:
    _, row = await _valid_refresh_row(db, token)
    row.revoked_at = datetime.now(tz=timezone.utc)
    await db.flush()
```

- [ ] **Step 6: `router.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditWriter
from app.core.db import get_session
from app.core.errors import ProblemException
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])
_audit = AuditWriter()


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_session)) -> TokenPair:
    user = await service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise ProblemException(401, "Invalid Credentials", "Email or password is incorrect.")
    tokens = await service.issue_tokens(db, user)
    await _audit.record(db, action="auth.login", object_type="user", object_id=str(user.id))
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_session)) -> TokenPair:
    tokens = await service.rotate(db, payload.refresh_token)
    await db.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_session)) -> None:
    await service.revoke(db, payload.refresh_token)
    await _audit.record(db, action="auth.logout", object_type="session")
    await db.commit()
```

- [ ] **Step 7: Include router in `main.py`**

Add `from app.modules.auth.router import router as auth_router` and `app.include_router(auth_router, prefix="/api/v1")`. (Also update health include to keep `/health` un-prefixed — health stays at root; API resources live under `/api/v1`.)

> Adjust the auth test paths to `/api/v1/auth/...` if you prefix here. To keep Task 7 tests as written, include the auth router with `prefix="/api/v1"` and update the test URLs to `/api/v1/auth/login` etc. Decide once and stay consistent (BRD §8 mandates `/api/v1`). **Chosen: prefix all resource routers with `/api/v1`; health stays at root.** Update the Task 7 test URLs accordingly.

- [ ] **Step 8: Run tests** (with `/api/v1` prefix in URLs)

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/auth backend/app/main.py backend/tests/test_auth.py
git commit -m "feat(PLT-01): login, refresh with rotation, logout with revocation + audit"
```

---

## Task 8: Password reset (token gen/verify; SMTP stubbed)

**Files:**
- Modify: `backend/app/modules/auth/models.py` (add `PasswordResetToken`), `schemas.py`, `service.py`, `router.py`
- Create: `backend/app/core/mail.py` (stub sender that logs)
- Test: extend `backend/tests/test_auth.py`

**Interfaces:**
- Produces:
  - Model `PasswordResetToken` (user_id, token_hash unique, expires_at, used_at).
  - `service.begin_password_reset(db, email) -> str | None` (returns raw token for the stub mailer; None if no user — but endpoint always 202 to avoid enumeration).
  - `service.confirm_password_reset(db, raw_token, new_password) -> None`.
  - Endpoints `POST /api/v1/auth/password-reset` (202 always) and `POST /api/v1/auth/password-reset/confirm`.
  - `app.core.mail.send_email(to, subject, body) -> None` (logs only in Slice 0).

- [ ] **Step 1: Failing test**

```python
import pytest

from app.core.rbac import Roles
from app.modules.auth import service as auth_service
from app.modules.users import service as users_service


@pytest.mark.asyncio
async def test_password_reset_flow(client, db_session):
    await users_service.create_user(
        db_session, email="u@x.com", full_name="U", password="oldpass12", role_names=[Roles.REQUESTER]
    )
    raw = await auth_service.begin_password_reset(db_session, "u@x.com")
    assert raw is not None
    await auth_service.confirm_password_reset(db_session, raw, "newpass123")
    # old password now fails, new works
    assert await auth_service.authenticate(db_session, "u@x.com", "oldpass12") is None
    assert await auth_service.authenticate(db_session, "u@x.com", "newpass123") is not None


@pytest.mark.asyncio
async def test_password_reset_request_always_202(client, db_session):
    resp = await client.post("/api/v1/auth/password-reset", json={"email": "nobody@x.com"})
    assert resp.status_code == 202
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_auth.py -k password_reset -v`
Expected: FAIL.

- [ ] **Step 3: `core/mail.py`**

```python
import logging

logger = logging.getLogger("mail")


def send_email(to: str, subject: str, body: str) -> None:
    # Slice 0: SMTP delivery is stubbed. Real delivery lands with PLT-04.
    logger.info("email.send", extra={"to": to, "subject": subject})
```

- [ ] **Step 4: Add `PasswordResetToken` to `auth/models.py`**

```python
import hashlib


class PasswordResetToken(UUIDAuditMixin, Base):
    __tablename__ = "password_reset_tokens"
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5: Add schemas** to `auth/schemas.py`

```python
class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
```

- [ ] **Step 6: Add service functions** to `auth/service.py`

```python
import hashlib
import secrets

from app.core.security import hash_password
from app.modules.auth.models import PasswordResetToken


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def begin_password_reset(db: AsyncSession, email: str) -> str | None:
    user = await get_by_email(db, email)
    if user is None:
        return None
    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=_hash_token(raw),
        expires_at=datetime.now(tz=timezone.utc) + timedelta(hours=1),
    ))
    await db.flush()
    return raw


async def confirm_password_reset(db: AsyncSession, raw_token: str, new_password: str) -> None:
    from app.core.errors import ProblemException
    row = (await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(raw_token))
    )).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at < datetime.now(tz=timezone.utc):
        raise ProblemException(400, "Invalid Token", "Reset token is invalid or expired.")
    user = await db.get(User, row.user_id)
    user.password_hash = hash_password(new_password)
    row.used_at = datetime.now(tz=timezone.utc)
    await db.flush()
```

- [ ] **Step 7: Add endpoints** to `auth/router.py`

```python
from app.core.mail import send_email
from app.modules.auth.schemas import PasswordResetConfirm, PasswordResetRequest


@router.post("/password-reset", status_code=202)
async def password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_session)) -> dict:
    raw = await service.begin_password_reset(db, payload.email)
    if raw is not None:
        send_email(payload.email, "Password reset", f"Reset token: {raw}")
        await _audit.record(db, action="auth.password_reset_requested", object_type="user")
    await db.commit()
    return {"status": "accepted"}


@router.post("/password-reset/confirm", status_code=204)
async def password_reset_confirm(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_session)) -> None:
    await service.confirm_password_reset(db, payload.token, payload.new_password)
    await _audit.record(db, action="auth.password_reset_confirmed", object_type="user")
    await db.commit()
```

- [ ] **Step 8: Run tests**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/modules/auth backend/app/core/mail.py backend/tests/test_auth.py
git commit -m "feat(PLT-01): password reset token flow with stubbed email delivery"
```

---

## Task 9: Users HTTP module — CRUD, invite, assign roles, deactivate (audited)

**Files:**
- Create: `backend/app/modules/users/schemas.py`, `backend/app/modules/users/router.py`
- Modify: `backend/app/main.py` (include users router), `backend/app/modules/users/service.py` (add list/get/invite helpers)
- Test: extend `backend/tests/test_users.py` with HTTP tests

**Interfaces:**
- Consumes: `require_roles(Roles.ADMIN)` (Task 5), `AuditWriter` (Task 6), service (Task 4).
- Produces endpoints (all under `/api/v1`, Admin-only):
  - `GET /users` (paginated: `?page=1&page_size=25`), `GET /users/{id}`, `POST /users` (invite: creates user, emails temp password), `POST /users/{id}/roles` (set roles), `POST /users/{id}/deactivate`.
  - Schemas `UserOut`, `UserCreate`, `RoleAssign`, `PageMeta`.

- [ ] **Step 1: Failing test**

```python
import pytest

from app.core.rbac import Roles
from app.core.security import create_access_token
from app.modules.users import service as users_service


async def _admin_headers(db):
    admin = await users_service.create_user(
        db, email="root@x.com", full_name="Root", password="pw123456", role_names=[Roles.ADMIN]
    )
    token = create_access_token(sub=str(admin.id), roles=[Roles.ADMIN], jti="j")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_admin_can_create_and_list_users(client, db_session):
    headers = await _admin_headers(db_session)
    resp = await client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "new@x.com", "full_name": "New", "role_names": [Roles.REQUESTER]},
    )
    assert resp.status_code == 201
    listing = await client.get("/api/v1/users", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 2


@pytest.mark.asyncio
async def test_non_admin_forbidden(client, db_session):
    user = await users_service.create_user(
        db_session, email="req@x.com", full_name="R", password="pw123456", role_names=[Roles.REQUESTER]
    )
    token = create_access_token(sub=str(user.id), roles=[Roles.REQUESTER], jti="j")
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deactivate_writes_audit(client, db_session):
    from sqlalchemy import select
    from app.core.audit import AuditLog

    headers = await _admin_headers(db_session)
    created = (await client.post(
        "/api/v1/users", headers=headers,
        json={"email": "t@x.com", "full_name": "T", "role_names": [Roles.REQUESTER]},
    )).json()
    resp = await client.post(f"/api/v1/users/{created['id']}/deactivate", headers=headers)
    assert resp.status_code == 200
    rows = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "user.deactivate")
    )).scalars().all()
    assert len(rows) == 1
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_users.py -k "http or admin or forbidden or deactivate" -v`
Expected: FAIL.

- [ ] **Step 3: `schemas.py`**

```python
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role_names: list[str] = []


class RoleAssign(BaseModel):
    role_names: list[str]


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    roles: list[RoleOut]


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserPage(BaseModel):
    data: list[UserOut]
    meta: PageMeta
```

- [ ] **Step 4: Add service helpers** to `users/service.py`

```python
import secrets

from sqlalchemy import func


async def list_users(db: AsyncSession, page: int, page_size: int) -> tuple[list[User], int]:
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    rows = (
        await db.execute(select(User).order_by(User.created_at).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return list(rows), total


async def get_user(db: AsyncSession, user_id) -> User | None:
    return await db.get(User, user_id)


async def invite_user(db: AsyncSession, *, email: str, full_name: str, role_names: list[str]) -> tuple[User, str]:
    temp_password = secrets.token_urlsafe(12)
    user = await create_user(db, email=email, full_name=full_name, password=temp_password, role_names=role_names)
    return user, temp_password
```

- [ ] **Step 5: `router.py`**

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditWriter
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.mail import send_email
from app.core.rbac import Roles, require_roles
from app.modules.users import service
from app.modules.users.schemas import (
    PageMeta, RoleAssign, UserCreate, UserOut, UserPage,
)

router = APIRouter(prefix="/users", tags=["users"])
_audit = AuditWriter()


@router.get("", response_model=UserPage)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> UserPage:
    rows, total = await service.list_users(db, page, page_size)
    return UserPage(
        data=[UserOut.model_validate(u) for u in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> UserOut:
    if await service.get_by_email(db, payload.email):
        raise ProblemException(409, "Conflict", "A user with this email already exists.")
    user, temp_password = await service.invite_user(
        db, email=payload.email, full_name=payload.full_name, role_names=payload.role_names
    )
    send_email(payload.email, "You've been invited to OpenP2P", f"Temp password: {temp_password}")
    await _audit.record(db, action="user.create", object_type="user", object_id=str(user.id),
                        after={"email": user.email, "roles": payload.role_names})
    await db.commit()
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> UserOut:
    user = await service.get_user(db, user_id)
    if user is None:
        raise ProblemException(404, "Not Found", "User not found.")
    return UserOut.model_validate(user)


@router.post("/{user_id}/roles", response_model=UserOut)
async def assign_roles(
    user_id: uuid.UUID,
    payload: RoleAssign,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> UserOut:
    user = await service.get_user(db, user_id)
    if user is None:
        raise ProblemException(404, "Not Found", "User not found.")
    before = [r.name for r in user.roles]
    await service.set_roles(db, user, payload.role_names)
    await _audit.record(db, action="user.set_roles", object_type="user", object_id=str(user.id),
                        before={"roles": before}, after={"roles": payload.role_names})
    await db.commit()
    return UserOut.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> UserOut:
    user = await service.get_user(db, user_id)
    if user is None:
        raise ProblemException(404, "Not Found", "User not found.")
    await service.deactivate(db, user)
    await _audit.record(db, action="user.deactivate", object_type="user", object_id=str(user.id),
                        after={"is_active": False})
    await db.commit()
    return UserOut.model_validate(user)
```

> Note on `require_roles` as a non-injected guard: because `require_roles(...)` returns `Depends(...)`, declaring it as a parameter default (`_: object = require_roles(...)`) registers the dependency. Keep the parameter even though it is unused.

- [ ] **Step 6: Include router** in `main.py`: `from app.modules.users.router import router as users_router` and `app.include_router(users_router, prefix="/api/v1")`.

- [ ] **Step 7: Run tests**

Run: `cd backend && pytest tests/test_users.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/users backend/app/main.py backend/tests/test_users.py
git commit -m "feat(PLT-02): admin user CRUD, invite, role assignment, deactivate with audit"
```

---

## Task 10: Storage backend interface + readiness health (DB, Redis, storage)

**Files:**
- Create: `backend/app/core/storage.py`
- Modify: `backend/app/health/router.py` (add `/health/ready`)
- Test: `backend/tests/test_health.py` (add readiness test), `backend/tests/test_storage.py`

**Interfaces:**
- Produces:
  - `StorageBackend` ABC: `async def save(self, key, data: bytes) -> str`, `async def open(self, key) -> bytes`, `async def delete(self, key) -> None`, `def url_for(self, key) -> str`; `generate_key(suffix="") -> str` helper (random, never user filename).
  - `LocalStorage(root)`; `get_storage() -> StorageBackend` factory selecting by `settings.storage_backend`.
  - `GET /health/ready` → `{"status":"ready","checks":{"db":true,"redis":true,"storage":true}}`, HTTP 503 if any check fails.

- [ ] **Step 1: Failing tests** — `test_storage.py`

```python
import pytest

from app.core.storage import LocalStorage


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path):
    store = LocalStorage(str(tmp_path))
    key = store.generate_key(".txt")
    await store.save(key, b"hello")
    assert await store.open(key) == b"hello"
    await store.delete(key)


def test_generate_key_is_random_not_filename():
    store = LocalStorage("/tmp")
    k1 = store.generate_key(".pdf")
    k2 = store.generate_key(".pdf")
    assert k1 != k2 and k1.endswith(".pdf")
```

Add to `test_health.py`:

```python
@pytest.mark.asyncio
async def test_health_ready(client):
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)
    assert "checks" in resp.json()
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_storage.py tests/test_health.py -v`
Expected: FAIL on storage import.

- [ ] **Step 3: `storage.py`**

```python
import os
import uuid
from abc import ABC, abstractmethod

from app.core.config import settings


class StorageBackend(ABC):
    def generate_key(self, suffix: str = "") -> str:
        return f"{uuid.uuid4().hex}{suffix}"

    @abstractmethod
    async def save(self, key: str, data: bytes) -> str: ...

    @abstractmethod
    async def open(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...


class LocalStorage(StorageBackend):
    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.root, key)

    async def save(self, key: str, data: bytes) -> str:
        with open(self._path(key), "wb") as f:
            f.write(data)
        return key

    async def open(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def url_for(self, key: str) -> str:
        return f"/files/{key}"


def get_storage() -> StorageBackend:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_root)
    raise NotImplementedError(f"storage backend {settings.storage_backend} not implemented in Slice 0")
```

- [ ] **Step 4: Readiness endpoint** — replace `health/router.py`

```python
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_session)) -> dict:
    checks = {"db": False, "redis": False, "storage": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        store = get_storage()
        key = store.generate_key(".probe")
        await store.save(key, b"ok")
        await store.delete(key)
        checks["storage"] = True
    except Exception:  # noqa: BLE001
        pass
    ok = all(checks.values())
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "degraded", "checks": checks}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_storage.py tests/test_health.py -v`
Expected: PASS (readiness returns 200 when Redis+DB+storage reachable, else 503).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/storage.py backend/app/health/router.py backend/tests/test_storage.py backend/tests/test_health.py
git commit -m "feat(PLT-07): pluggable storage interface and readiness health with dependency checks"
```

---

## Task 11: ARQ worker skeleton

**Files:**
- Create: `backend/app/worker.py`
- Test: `backend/tests/test_worker.py`

**Interfaces:**
- Produces:
  - `async def example_task(ctx, payload: dict) -> dict` — idempotent no-op that echoes and logs.
  - `class WorkerSettings` with `functions = [example_task]`, `redis_settings` from `settings.redis_url`, `on_startup`/`on_shutdown`.

- [ ] **Step 1: Failing test** (unit-test the task function directly; no Redis needed)

```python
import pytest

from app.worker import example_task


@pytest.mark.asyncio
async def test_example_task_is_idempotent_echo():
    out1 = await example_task({}, {"id": "abc"})
    out2 = await example_task({}, {"id": "abc"})
    assert out1 == out2 == {"processed": "abc"}
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_worker.py -v`
Expected: FAIL.

- [ ] **Step 3: `worker.py`**

```python
import logging

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger("worker")


async def example_task(ctx: dict, payload: dict) -> dict:
    # Idempotent: derives output purely from input; safe to retry.
    logger.info("example_task", extra={"payload_id": payload.get("id")})
    return {"processed": payload["id"]}


async def _on_startup(ctx: dict) -> None:
    setup_logging()
    logger.info("worker.startup")


async def _on_shutdown(ctx: dict) -> None:
    logger.info("worker.shutdown")


class WorkerSettings:
    functions = [example_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = _on_startup
    on_shutdown = _on_shutdown
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_worker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker.py backend/tests/test_worker.py
git commit -m "feat: ARQ worker skeleton with idempotent example task"
```

---

## Task 12: Alembic async migrations (initial schema)

**Files:**
- Create: `backend/alembic.ini`, `backend/app/alembic/env.py`, `backend/app/alembic/script.py.mako`, `backend/app/alembic/versions/0001_initial.py`
- Test: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `alembic upgrade head` builds all Slice 0 tables (users, roles, user_roles, refresh_tokens, password_reset_tokens, audit_log) on a fresh DB.

- [ ] **Step 1: `alembic.ini`** (key lines)

```ini
[alembic]
script_location = app/alembic
sqlalchemy.url =
[loggers]
keys = root
[handlers]
keys = console
[formatters]
keys = generic
[logger_root]
level = WARN
handlers = console
[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic
[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

- [ ] **Step 2: `app/alembic/env.py`** (async)

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models.base import Base
# Import all models so metadata is populated:
import app.modules.users.models  # noqa: F401
import app.modules.auth.models  # noqa: F401
import app.core.audit  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def _run_sync(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
```

- [ ] **Step 3: `script.py.mako`** — use Alembic's default template (copy the standard mako from `alembic init` output).

- [ ] **Step 4: Generate the initial migration**

Run: `cd backend && DATABASE_URL=postgresql+asyncpg://openp2p:openp2p@localhost:5432/openp2p alembic revision --autogenerate -m "initial"`
Rename the generated file to `0001_initial.py`. Verify it creates all six tables with UUID pks, timestamptz columns, unique/index constraints, and JSONB on `audit_log.before/after`.

- [ ] **Step 5: Migration smoke test** — `test_migrations.py`

```python
import subprocess


def test_alembic_upgrade_head_runs():
    # Requires a reachable throwaway DB via ALEMBIC_TEST_URL / DATABASE_URL.
    result = subprocess.run(
        ["alembic", "upgrade", "head"], cwd="backend", capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 6: Run**

Run: `cd backend && alembic upgrade head && pytest tests/test_migrations.py -v`
Expected: PASS; tables exist in the target DB.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/app/alembic backend/tests/test_migrations.py
git commit -m "feat: async Alembic env and initial migration for Slice 0 schema"
```

---

## Task 13: Seed script + Makefile + docker-compose + Dockerfiles + .env.example

**Files:**
- Create: `backend/app/seed.py`, `Makefile`, `docker/docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.env.example`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Produces:
  - `async def run_seed() -> None` — idempotent; ensures 8 roles + one Admin user exist.
  - `make up | migrate | seed-demo | test | lint` targets.
  - Compose stack: postgres, redis, api, worker, frontend, (optional) minio.

- [ ] **Step 1: Failing test** — `test_seed.py`

```python
import pytest
from sqlalchemy import func, select

from app.core.rbac import ALL_ROLES
from app.modules.users.models import Role, User
from app.seed import seed_with_session


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    await seed_with_session(db_session)
    await seed_with_session(db_session)  # second run must not duplicate
    roles = (await db_session.execute(select(func.count()).select_from(Role))).scalar_one()
    admins = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert roles == len(ALL_ROLES)
    assert admins == 1
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && pytest tests/test_seed.py -v`
Expected: FAIL.

- [ ] **Step 3: `seed.py`**

```python
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.rbac import ALL_ROLES, Roles
from app.modules.users import service


async def seed_with_session(db: AsyncSession) -> None:
    for role_name in ALL_ROLES:
        await service.get_or_create_role(db, role_name)
    if await service.get_by_email(db, settings.seed_admin_email) is None:
        await service.create_user(
            db,
            email=settings.seed_admin_email,
            full_name="Administrator",
            password=settings.seed_admin_password,
            role_names=[Roles.ADMIN],
        )
    await db.flush()


async def run_seed() -> None:
    async with SessionLocal() as db:
        await seed_with_session(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(run_seed())
```

- [ ] **Step 4: `.env.example`**

```bash
DATABASE_URL=postgresql+asyncpg://openp2p:openp2p@postgres:5432/openp2p
REDIS_URL=redis://redis:6379/0
SECRET_KEY=change-me
SECRET_ENCRYPTION_KEY=change-me-32-bytes-base64
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=7
STORAGE_BACKEND=local
STORAGE_LOCAL_ROOT=/data/storage
FRONTEND_ORIGIN=http://localhost:5173
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=admin
```

- [ ] **Step 5: `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 6: `frontend/Dockerfile`** (dev server; production build handled later)

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 7: `docker/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: openp2p
      POSTGRES_PASSWORD: openp2p
      POSTGRES_DB: openp2p
    ports: ["5432:5432"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openp2p"]
      interval: 5s
      timeout: 3s
      retries: 10
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: ../backend
    env_file: ../.env
    ports: ["8000:8000"]
    depends_on:
      postgres: {condition: service_healthy}
      redis: {condition: service_healthy}
    volumes: ["storage:/data/storage"]

  worker:
    build: ../backend
    env_file: ../.env
    command: ["arq", "app.worker.WorkerSettings"]
    depends_on:
      redis: {condition: service_healthy}
      postgres: {condition: service_healthy}
    volumes: ["storage:/data/storage"]

  frontend:
    build: ../frontend
    environment:
      VITE_API_BASE: http://localhost:8000/api/v1
    ports: ["5173:5173"]
    depends_on: ["api"]

  minio:
    image: minio/minio
    profiles: ["storage"]
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    ports: ["9000:9000", "9001:9001"]
    volumes: ["miniodata:/data"]

volumes:
  pgdata:
  storage:
  miniodata:
```

- [ ] **Step 8: `Makefile`**

```makefile
.PHONY: up down migrate seed-demo test lint

up:
	docker compose -f docker/docker-compose.yml up --build

down:
	docker compose -f docker/docker-compose.yml down

migrate:
	docker compose -f docker/docker-compose.yml run --rm api alembic upgrade head

seed-demo:
	docker compose -f docker/docker-compose.yml run --rm api python -m app.seed

test:
	cd backend && pytest -q
	cd frontend && npm run test --silent

lint:
	cd backend && ruff check . && mypy app
	cd frontend && npm run lint
```

- [ ] **Step 9: Run tests**

Run: `cd backend && pytest tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/seed.py backend/tests/test_seed.py Makefile docker/docker-compose.yml backend/Dockerfile frontend/Dockerfile .env.example
git commit -m "feat(NFR-OPS-01): idempotent seed, docker-compose stack, Dockerfiles, Makefile, .env.example"
```

---

## Task 14: Frontend shell — Vite/React/TS, auth context, login, protected route, landing, i18n

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/src/lib/api.ts`, `frontend/src/lib/queryClient.ts`, `frontend/src/i18n/index.ts`, `frontend/src/i18n/en.json`, `frontend/src/auth/AuthContext.tsx`, `frontend/src/auth/ProtectedRoute.tsx`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/components/Layout.tsx`, `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`, `frontend/src/__tests__/Login.test.tsx`

**Interfaces:**
- Consumes: backend `/api/v1/auth/login`, `/api/v1/auth/refresh`, and a `GET /api/v1/me` endpoint.
- Produces: a running SPA where logging in stores tokens and renders the current user + roles.

> **Backend addition required first:** add `GET /api/v1/me` returning the current user. Do this as sub-step 0 below.

- [ ] **Step 0: Add `/me` endpoint (backend) + test**

In `backend/app/modules/users/router.py` add:

```python
from app.core.deps import get_current_active_user
from app.modules.users.models import User as UserModel


@router.get("/me/profile", response_model=UserOut)
async def me(user: UserModel = Depends(get_current_active_user)) -> UserOut:
    return UserOut.model_validate(user)
```

Add test to `tests/test_users.py`:

```python
@pytest.mark.asyncio
async def test_me_returns_current_user(client, db_session):
    from app.core.security import create_access_token
    user = await users_service.create_user(
        db_session, email="me@x.com", full_name="Me", password="pw123456", role_names=[Roles.ADMIN]
    )
    token = create_access_token(sub=str(user.id), roles=[Roles.ADMIN], jti="j")
    resp = await client.get("/api/v1/users/me/profile", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@x.com"
```

Run: `cd backend && pytest tests/test_users.py -k me -v` → PASS. Commit.

- [ ] **Step 1: `package.json`**

```json
{
  "name": "openp2p-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint src --max-warnings=0",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.51.0",
    "i18next": "^23.12.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-i18next": "^15.0.0",
    "react-router-dom": "^6.25.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.7.0",
    "jsdom": "^24.1.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Config files**

`vite.config.ts`:
```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({ plugins: [react()], server: { port: 5173 } });
```

`vitest.config.ts`:
```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./vitest.setup.ts"], globals: true },
});
```

`vitest.setup.ts`:
```typescript
import "@testing-library/jest-dom";
```

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020", "useDefineForClassFields": true, "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext", "skipLibCheck": true, "moduleResolution": "bundler",
    "resolveJsonModule": true, "isolatedModules": true, "noEmit": true, "jsx": "react-jsx",
    "strict": true, "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"]
}
```

`tailwind.config.js`:
```javascript
export default { content: ["./index.html", "./src/**/*.{ts,tsx}"], theme: { extend: {} }, plugins: [] };
```

`postcss.config.js`:
```javascript
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

`index.html`:
```html
<!doctype html>
<html lang="en">
  <head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>OpenP2P</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body>
</html>
```

`src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: i18n** — `src/i18n/en.json`

```json
{
  "login": { "title": "Sign in to OpenP2P", "email": "Email", "password": "Password", "submit": "Sign in", "error": "Invalid email or password" },
  "home": { "welcome": "Welcome, {{name}}", "roles": "Your roles", "logout": "Log out" }
}
```

`src/i18n/index.ts`:
```typescript
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";

i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});
export default i18n;
```

- [ ] **Step 4: API client** — `src/lib/api.ts`

```typescript
const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const getRefreshToken = () => localStorage.getItem("refresh_token");
export const setRefreshToken = (t: string | null) =>
  t ? localStorage.setItem("refresh_token", t) : localStorage.removeItem("refresh_token");

async function refresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  const resp = await fetch(`${BASE}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  });
  if (!resp.ok) return false;
  const data = await resp.json();
  setAccessToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return true;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const resp = await fetch(`${BASE}${path}`, { ...init, headers });
  if (resp.status === 401 && retry && (await refresh())) return apiFetch(path, init, false);
  return resp;
}

export async function login(email: string, password: string) {
  const resp = await fetch(`${BASE}/auth/login`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) throw new Error("login_failed");
  return resp.json() as Promise<{ access_token: string; refresh_token: string }>;
}
```

`src/lib/queryClient.ts`:
```typescript
import { QueryClient } from "@tanstack/react-query";
export const queryClient = new QueryClient();
```

- [ ] **Step 5: Auth context** — `src/auth/AuthContext.tsx`

```tsx
import { createContext, useContext, useState, type ReactNode } from "react";
import { apiFetch, login as apiLogin, setAccessToken, setRefreshToken } from "../lib/api";

type User = { id: string; email: string; full_name: string; roles: { name: string }[] };
type AuthState = { user: User | null; signIn: (e: string, p: string) => Promise<void>; signOut: () => void };

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  async function signIn(email: string, password: string) {
    const tokens = await apiLogin(email, password);
    setAccessToken(tokens.access_token);
    setRefreshToken(tokens.refresh_token);
    const me = await apiFetch("/users/me/profile");
    if (!me.ok) throw new Error("profile_failed");
    setUser(await me.json());
  }

  function signOut() {
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
  }

  return <Ctx.Provider value={{ user, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside provider");
  return v;
}
```

`src/auth/ProtectedRoute.tsx`:
```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import type { ReactNode } from "react";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}
```

- [ ] **Step 6: Pages + layout**

`src/pages/Login.tsx`:
```tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(false);
    try {
      await signIn(email, password);
      navigate("/");
    } catch {
      setError(true);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mx-auto mt-24 flex max-w-sm flex-col gap-3">
      <h1 className="text-xl font-semibold">{t("login.title")}</h1>
      <input aria-label={t("login.email")} className="border p-2" value={email}
        onChange={(e) => setEmail(e.target.value)} placeholder={t("login.email")} />
      <input aria-label={t("login.password")} type="password" className="border p-2" value={password}
        onChange={(e) => setPassword(e.target.value)} placeholder={t("login.password")} />
      {error && <p role="alert" className="text-red-600">{t("login.error")}</p>}
      <button type="submit" className="bg-black p-2 text-white">{t("login.submit")}</button>
    </form>
  );
}
```

`src/components/Layout.tsx`:
```tsx
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../auth/AuthContext";

export default function Layout({ children }: { children: ReactNode }) {
  const { signOut } = useAuth();
  const { t } = useTranslation();
  return (
    <div>
      <header className="flex justify-between border-b p-4">
        <span className="font-semibold">OpenP2P</span>
        <button onClick={signOut} className="text-sm underline">{t("home.logout")}</button>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
```

`src/pages/Home.tsx`:
```tsx
import { useTranslation } from "react-i18next";
import Layout from "../components/Layout";
import { useAuth } from "../auth/AuthContext";

export default function Home() {
  const { t } = useTranslation();
  const { user } = useAuth();
  return (
    <Layout>
      <h1 className="text-lg">{t("home.welcome", { name: user?.full_name })}</h1>
      <p className="mt-2 text-sm text-gray-600">{user?.email}</p>
      <h2 className="mt-4 font-medium">{t("home.roles")}</h2>
      <ul className="list-disc pl-6">{user?.roles.map((r) => <li key={r.name}>{r.name}</li>)}</ul>
    </Layout>
  );
}
```

- [ ] **Step 7: App + main**

`src/App.tsx`:
```tsx
import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import Home from "./pages/Home";
import Login from "./pages/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Home /></ProtectedRoute>} />
    </Routes>
  );
}
```

`src/main.tsx`:
```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import "./i18n";
import "./index.css";
import { queryClient } from "./lib/queryClient";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 8: Smoke test** — `src/__tests__/Login.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrowserRouter } from "react-router-dom";
import Login from "../pages/Login";
import { AuthProvider } from "../auth/AuthContext";
import "../i18n";

describe("Login", () => {
  it("renders the sign-in form", () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Login />
        </BrowserRouter>
      </AuthProvider>
    );
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Install & run tests**

Run: `cd frontend && npm install && npm run test`
Expected: PASS (1 test).

- [ ] **Step 10: Commit**

```bash
git add frontend
git commit -m "feat: React shell with auth context, login, protected route, i18n, landing page"
```

---

## Task 15: End-to-end verification & acceptance

**Files:** none (verification only); optionally `docs/superpowers/plans/slice0-verification.md` notes.

- [ ] **Step 1:** From a clean clone, copy `.env.example` to `.env`, run `make up` (all five services start; postgres+redis healthy).
- [ ] **Step 2:** In another shell: `make migrate && make seed-demo` (schema built; roles + admin seeded; re-run `make seed-demo` → no duplicates).
- [ ] **Step 3:** Open `http://localhost:5173`, log in as `admin@example.com` / `admin`; confirm the landing page shows the email and `Admin` role.
- [ ] **Step 4:** With the admin access token, `POST /api/v1/users` to create a user, `POST /api/v1/users/{id}/roles`, `POST /api/v1/users/{id}/deactivate`; confirm a `Requester`-only token gets 403 on `GET /api/v1/users`.
- [ ] **Step 5:** Query `audit_log`: confirm rows for `auth.login`, `user.create`, `user.set_roles`, `user.deactivate`, each with actor + IP; confirm there is no update/delete route for audit.
- [ ] **Step 6:** `curl /health` → 200; `curl /health/ready` → 200 with all checks true; stop redis and confirm `/health/ready` → 503.
- [ ] **Step 7:** `make test` (backend + frontend green); `make lint` clean.
- [ ] **Step 8:** Confirm an error (e.g. bad login) returns `application/problem+json`.
- [ ] **Step 9:** Merge branch `slice0-foundation` per the finishing-a-development-branch skill.

---

## Self-Review

**Spec coverage:**
- Repo scaffolding → Tasks 1, 13, 14. docker-compose/Dockerfiles/Makefile/.env → Task 13. Async DB + Alembic → Tasks 3, 12. Base model mixin → Task 3. Auth (PLT-01) → Tasks 2, 7, 8. RBAC (NFR-SEC-01) → Task 5. User mgmt (PLT-02) → Tasks 4, 9. Audit log (PLT-06) → Task 6 (used in 7, 8, 9). Health/ops (PLT-07) → Tasks 1, 10. Storage interface → Task 10. Worker skeleton → Task 11. Seed → Task 13. Frontend shell → Task 14. RFC 7807 → Task 1. i18n (NFR-I18N-01) → Task 14. Acceptance criteria → Task 15. **All spec sections covered.**
- Deferred items (S3, real SMTP, settings/dashboard UI, business modules) correctly excluded.

**Placeholder scan:** No TBD/TODO left. Two inline shortcuts are explicitly flagged with replacement instructions (the `__import__("uuid")` note in Task 5; the `/api/v1` prefix decision in Task 7). `script.py.mako` points to Alembic's standard template rather than reproducing boilerplate.

**Type consistency:** `create_user(..., role_names=...)` used consistently (Tasks 4, 9, 13). `require_roles(*roles)` returns `Depends(...)` and is used as a parameter default everywhere (Tasks 5, 9). `TokenPair` fields (`access_token`, `refresh_token`, `token_type`) consistent across service/router/frontend (Tasks 7, 14). `AuditWriter.record(db, *, action, object_type, object_id, before, after)` signature consistent across Tasks 6/7/8/9. `get_current_active_user` used by both `require_roles` and `/me` (Tasks 5, 14). Audit context: `set_audit_context` (Task 6) + `set_audit_actor` wired in deps (Task 6 step 5).

**Fix applied during review:** Task 7 originally left auth routes unprefixed while the users router used `/api/v1`; standardized on `/api/v1` for all resource routers (health at root) and noted the test-URL implication inline.
