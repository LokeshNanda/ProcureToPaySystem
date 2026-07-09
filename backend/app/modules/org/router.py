import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditWriter
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.rbac import Roles, require_roles
from app.modules.org import csv_import, service
from app.modules.org.schemas import (
    CostCenterCreate, CostCenterOut, CostCenterPage, CostCenterUpdate,
    GLAccountCreate, GLAccountOut, GLAccountPage, GLAccountUpdate, ImportResult,
)
from app.modules.users.schemas import PageMeta

_audit = AuditWriter()
cost_center_router = APIRouter(prefix="/cost-centers", tags=["cost-centers"])
gl_account_router = APIRouter(prefix="/gl-accounts", tags=["gl-accounts"])


def _active_filter(active: str) -> bool | None:
    return {"true": True, "false": False, "all": None}[active]


# ---------- Cost centers ----------
@cost_center_router.get("", response_model=CostCenterPage)
async def list_cost_centers(
    active: str = Query("all", pattern="^(true|false|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> CostCenterPage:
    rows, total = await service.list_cost_centers(db, active=_active_filter(active), page=page, page_size=page_size)
    return CostCenterPage(
        data=[CostCenterOut.model_validate(r) for r in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@cost_center_router.post("", response_model=CostCenterOut, status_code=201)
async def create_cost_center(
    payload: CostCenterCreate,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> CostCenterOut:
    cc = await service.create_cost_center(db, code=payload.code, name=payload.name, owner_id=payload.owner_id)
    await _audit.record(db, action="cost_center.create", object_type="cost_center", object_id=str(cc.id),
                        after={"code": cc.code, "name": cc.name})
    await db.commit()
    return CostCenterOut.model_validate(cc)


@cost_center_router.get("/{cc_id}", response_model=CostCenterOut)
async def get_cost_center(
    cc_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> CostCenterOut:
    cc = await service.get_cost_center(db, cc_id)
    if cc is None:
        raise ProblemException(404, "Not Found", "Cost center not found.")
    return CostCenterOut.model_validate(cc)


@cost_center_router.patch("/{cc_id}", response_model=CostCenterOut)
async def update_cost_center(
    cc_id: uuid.UUID,
    payload: CostCenterUpdate,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> CostCenterOut:
    cc = await service.get_cost_center(db, cc_id)
    if cc is None:
        raise ProblemException(404, "Not Found", "Cost center not found.")
    fields = payload.model_dump(exclude_unset=True)
    before = {"name": cc.name, "owner_id": str(cc.owner_id) if cc.owner_id else None}
    if "owner_id" in fields:
        await service.update_cost_center(db, cc, name=fields.get("name"), owner_id=payload.owner_id)
    else:
        await service.update_cost_center(db, cc, name=fields.get("name"))
    await _audit.record(db, action="cost_center.update", object_type="cost_center", object_id=str(cc.id),
                        before=before, after={"name": cc.name, "owner_id": str(cc.owner_id) if cc.owner_id else None})
    await db.commit()
    return CostCenterOut.model_validate(cc)


@cost_center_router.post("/{cc_id}/deactivate", response_model=CostCenterOut)
async def deactivate_cost_center(
    cc_id: uuid.UUID, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> CostCenterOut:
    return await _set_cc_active(db, cc_id, False)


@cost_center_router.post("/{cc_id}/reactivate", response_model=CostCenterOut)
async def reactivate_cost_center(
    cc_id: uuid.UUID, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> CostCenterOut:
    return await _set_cc_active(db, cc_id, True)


async def _set_cc_active(db, cc_id, active: bool) -> CostCenterOut:
    cc = await service.get_cost_center(db, cc_id)
    if cc is None:
        raise ProblemException(404, "Not Found", "Cost center not found.")
    await service.set_cost_center_active(db, cc, active)
    await _audit.record(db, action=f"cost_center.{'reactivate' if active else 'deactivate'}",
                        object_type="cost_center", object_id=str(cc.id), after={"is_active": active})
    await db.commit()
    return CostCenterOut.model_validate(cc)


@cost_center_router.post("/import", response_model=ImportResult)
async def import_cost_centers(
    file: UploadFile,
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> ImportResult:
    text = (await file.read()).decode("utf-8", errors="replace")
    result = await csv_import.import_cost_centers(db, text)
    await _audit.record(db, action="cost_center.import", object_type="cost_center",
                        after={"created": result["created"], "updated": result["updated"],
                               "error_count": len(result["errors"])})
    await db.commit()
    return ImportResult(**result)


# ---------- GL accounts ----------
@gl_account_router.get("", response_model=GLAccountPage)
async def list_gl_accounts(
    active: str = Query("all", pattern="^(true|false|all)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> GLAccountPage:
    rows, total = await service.list_gl_accounts(db, active=_active_filter(active), page=page, page_size=page_size)
    return GLAccountPage(
        data=[GLAccountOut.model_validate(r) for r in rows],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )


@gl_account_router.post("", response_model=GLAccountOut, status_code=201)
async def create_gl_account(
    payload: GLAccountCreate, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> GLAccountOut:
    gl = await service.create_gl_account(db, code=payload.code, name=payload.name)
    await _audit.record(db, action="gl_account.create", object_type="gl_account", object_id=str(gl.id),
                        after={"code": gl.code, "name": gl.name})
    await db.commit()
    return GLAccountOut.model_validate(gl)


@gl_account_router.get("/{gl_id}", response_model=GLAccountOut)
async def get_gl_account(
    gl_id: uuid.UUID, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> GLAccountOut:
    gl = await service.get_gl_account(db, gl_id)
    if gl is None:
        raise ProblemException(404, "Not Found", "GL account not found.")
    return GLAccountOut.model_validate(gl)


@gl_account_router.patch("/{gl_id}", response_model=GLAccountOut)
async def update_gl_account(
    gl_id: uuid.UUID, payload: GLAccountUpdate, db: AsyncSession = Depends(get_session),
    _: object = require_roles(Roles.ADMIN),
) -> GLAccountOut:
    gl = await service.get_gl_account(db, gl_id)
    if gl is None:
        raise ProblemException(404, "Not Found", "GL account not found.")
    before = {"name": gl.name}
    await service.update_gl_account(db, gl, name=payload.model_dump(exclude_unset=True).get("name"))
    await _audit.record(db, action="gl_account.update", object_type="gl_account", object_id=str(gl.id),
                        before=before, after={"name": gl.name})
    await db.commit()
    return GLAccountOut.model_validate(gl)


@gl_account_router.post("/{gl_id}/deactivate", response_model=GLAccountOut)
async def deactivate_gl_account(
    gl_id: uuid.UUID, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> GLAccountOut:
    return await _set_gl_active(db, gl_id, False)


@gl_account_router.post("/{gl_id}/reactivate", response_model=GLAccountOut)
async def reactivate_gl_account(
    gl_id: uuid.UUID, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> GLAccountOut:
    return await _set_gl_active(db, gl_id, True)


async def _set_gl_active(db, gl_id, active: bool) -> GLAccountOut:
    gl = await service.get_gl_account(db, gl_id)
    if gl is None:
        raise ProblemException(404, "Not Found", "GL account not found.")
    await service.set_gl_account_active(db, gl, active)
    await _audit.record(db, action=f"gl_account.{'reactivate' if active else 'deactivate'}",
                        object_type="gl_account", object_id=str(gl.id), after={"is_active": active})
    await db.commit()
    return GLAccountOut.model_validate(gl)


@gl_account_router.post("/import", response_model=ImportResult)
async def import_gl_accounts(
    file: UploadFile, db: AsyncSession = Depends(get_session), _: object = require_roles(Roles.ADMIN)
) -> ImportResult:
    text = (await file.read()).decode("utf-8", errors="replace")
    result = await csv_import.import_gl_accounts(db, text)
    await _audit.record(db, action="gl_account.import", object_type="gl_account",
                        after={"created": result["created"], "updated": result["updated"],
                               "error_count": len(result["errors"])})
    await db.commit()
    return ImportResult(**result)
