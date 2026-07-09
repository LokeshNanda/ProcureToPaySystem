import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import get_session
from app.main import create_app
from app.models.base import Base

# Later tasks register their models here so Base.metadata is fully populated,
# e.g.:
import app.modules.users.models  # noqa: F401  (added in Task 4)
import app.core.audit  # noqa: F401  (AuditLog model, added in Task 6)
#   import app.modules.auth.models  # noqa: F401   (added in Task 7)

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
    maker = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
        join_transaction_mode="create_savepoint",
    )
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
