import pytest

from app.core.rbac import Roles
from app.core.security import create_access_token
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


async def _admin_headers(db):
    admin = await service.create_user(
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
    user = await service.create_user(
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
