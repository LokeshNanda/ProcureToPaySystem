import pytest

from app.core.rbac import Roles
from app.modules.users import service as users_service


@pytest.mark.asyncio
async def test_login_success_and_me_flow(client, db_session):
    await users_service.create_user(
        db_session, email="admin@x.com", full_name="A",
        password="pw123456", role_names=[Roles.ADMIN],
    )
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "pw123456"})
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
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@x.com", "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_and_old_token_rejected(client, db_session):
    await users_service.create_user(
        db_session, email="a@x.com", full_name="A", password="pw123456", role_names=[Roles.ADMIN]
    )
    login = (await client.post("/api/v1/auth/login", json={"email": "a@x.com", "password": "pw123456"})).json()
    old_refresh = login["refresh_token"]
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r1.status_code == 200
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401  # old token was revoked on rotation


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client, db_session):
    await users_service.create_user(
        db_session, email="b@x.com", full_name="B", password="pw123456", role_names=[Roles.ADMIN]
    )
    login = (await client.post("/api/v1/auth/login", json={"email": "b@x.com", "password": "pw123456"})).json()
    refresh_token = login["refresh_token"]
    logout_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client, db_session):
    await users_service.create_user(
        db_session, email="c@x.com", full_name="C", password="pw123456", role_names=[Roles.ADMIN]
    )
    login = (await client.post("/api/v1/auth/login", json={"email": "c@x.com", "password": "pw123456"})).json()
    access_token = login["access_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token_401(client, db_session):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert resp.status_code == 401
