import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import get_session
from app.core.rbac import Roles, require_roles
from app.core.security import create_access_token, create_refresh_token
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


@pytest.mark.asyncio
async def test_malformed_sub_is_401_not_500(rbac_client):
    client, _ = rbac_client
    token = create_access_token(sub="not-a-uuid", roles=[Roles.ADMIN], jti="j")
    resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_is_403(rbac_client):
    client, db = rbac_client
    user = await service.create_user(
        db, email="inactive@x.com", full_name="I", password="pw123456", role_names=[Roles.ADMIN]
    )
    await service.deactivate(db, user)
    token = create_access_token(sub=str(user.id), roles=[Roles.ADMIN], jti="j")
    resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_access_token_is_401(rbac_client):
    client, db = rbac_client
    user = await service.create_user(
        db, email="refresh@x.com", full_name="F", password="pw123456", role_names=[Roles.ADMIN]
    )
    token = create_refresh_token(sub=str(user.id), jti="j")
    resp = await client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
