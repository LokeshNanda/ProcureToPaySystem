import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.errors import ProblemException
from app.core.rbac import Roles
from app.modules.auth import service as auth_service
from app.modules.auth.models import PasswordResetToken
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


@pytest.mark.asyncio
async def test_password_reset_token_is_single_use(client, db_session):
    await users_service.create_user(
        db_session, email="s@x.com", full_name="S", password="oldpass12", role_names=[Roles.REQUESTER]
    )
    raw = await auth_service.begin_password_reset(db_session, "s@x.com")
    assert raw is not None
    await auth_service.confirm_password_reset(db_session, raw, "newpass123")
    # replay with the same raw token must be rejected
    with pytest.raises(ProblemException) as exc:
        await auth_service.confirm_password_reset(db_session, raw, "another-pw")
    assert exc.value.status == 400


@pytest.mark.asyncio
async def test_password_reset_confirm_revokes_outstanding_refresh_tokens(client, db_session):
    await users_service.create_user(
        db_session, email="revoke@x.com", full_name="R", password="oldpass12", role_names=[Roles.REQUESTER]
    )
    login = (await client.post(
        "/api/v1/auth/login", json={"email": "revoke@x.com", "password": "oldpass12"}
    )).json()
    pre_reset_refresh = login["refresh_token"]

    raw = await auth_service.begin_password_reset(db_session, "revoke@x.com")
    assert raw is not None
    await auth_service.confirm_password_reset(db_session, raw, "newpass123")

    with pytest.raises(ProblemException) as exc:
        await auth_service.rotate(db_session, pre_reset_refresh)
    assert exc.value.status == 401


@pytest.mark.asyncio
async def test_password_reset_expired_token_rejected(client, db_session):
    await users_service.create_user(
        db_session, email="e@x.com", full_name="E", password="oldpass12", role_names=[Roles.REQUESTER]
    )
    raw = await auth_service.begin_password_reset(db_session, "e@x.com")
    assert raw is not None
    row = (await db_session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        )
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.flush()
    with pytest.raises(ProblemException) as exc:
        await auth_service.confirm_password_reset(db_session, raw, "x")
    assert exc.value.status == 400
