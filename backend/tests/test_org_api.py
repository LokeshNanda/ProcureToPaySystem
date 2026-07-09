import io

import pytest

from app.core.rbac import Roles
from app.core.security import create_access_token
from app.modules.users import service as users_service


async def _admin_headers(db):
    admin = await users_service.create_user(
        db, email="admin-org@x.com", full_name="A", password="pw123456", role_names=[Roles.ADMIN]
    )
    return {"Authorization": f"Bearer {create_access_token(sub=str(admin.id), roles=[Roles.ADMIN], jti='j')}"}


@pytest.mark.asyncio
async def test_admin_creates_lists_and_deactivates_cost_center(client, db_session):
    h = await _admin_headers(db_session)
    r = await client.post("/api/v1/cost-centers", headers=h, json={"code": "4200", "name": "Marketing"})
    assert r.status_code == 201
    cc_id = r.json()["id"]
    dup = await client.post("/api/v1/cost-centers", headers=h, json={"code": "4200", "name": "x"})
    assert dup.status_code == 409
    d = await client.post(f"/api/v1/cost-centers/{cc_id}/deactivate", headers=h)
    assert d.status_code == 200 and d.json()["is_active"] is False
    active_only = await client.get("/api/v1/cost-centers?active=true", headers=h)
    assert active_only.json()["meta"]["total"] == 0


@pytest.mark.asyncio
async def test_non_admin_forbidden(client, db_session):
    user = await users_service.create_user(
        db_session, email="req-org@x.com", full_name="R", password="pw123456", role_names=[Roles.REQUESTER]
    )
    tok = create_access_token(sub=str(user.id), roles=[Roles.REQUESTER], jti="j")
    r = await client.get("/api/v1/cost-centers", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_gl_account_import_reports_rows_and_writes_audit(client, db_session):
    from sqlalchemy import select
    from app.core.audit import AuditLog

    h = await _admin_headers(db_session)
    csv_bytes = b"code,name\n6000,Supplies\n,bad\n6001,Travel\n"
    files = {"file": ("gl.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = await client.post("/api/v1/gl-accounts/import", headers=h, files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2 and len(body["errors"]) == 1
    rows = (await db_session.execute(select(AuditLog).where(AuditLog.action == "gl_account.import"))).scalars().all()
    assert len(rows) == 1 and rows[0].after["created"] == 2


@pytest.mark.asyncio
async def test_patch_cannot_change_code(client, db_session):
    h = await _admin_headers(db_session)
    r = await client.post("/api/v1/gl-accounts", headers=h, json={"code": "7000", "name": "Old"})
    gid = r.json()["id"]
    # code is not a field on the update schema; sending it is ignored, name updates
    p = await client.patch(f"/api/v1/gl-accounts/{gid}", headers=h, json={"code": "9999", "name": "New"})
    assert p.status_code == 200 and p.json()["code"] == "7000" and p.json()["name"] == "New"
