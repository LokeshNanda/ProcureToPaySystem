import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.modules.org.models import CostCenter, GLAccount

_UNSET = object()


async def get_cost_center(db: AsyncSession, id: uuid.UUID) -> CostCenter | None:
    return await db.get(CostCenter, id)


async def get_gl_account(db: AsyncSession, id: uuid.UUID) -> GLAccount | None:
    return await db.get(GLAccount, id)


async def get_cost_center_by_code(db: AsyncSession, code: str) -> CostCenter | None:
    return (await db.execute(select(CostCenter).where(CostCenter.code == code))).scalar_one_or_none()


async def get_gl_account_by_code(db: AsyncSession, code: str) -> GLAccount | None:
    return (await db.execute(select(GLAccount).where(GLAccount.code == code))).scalar_one_or_none()


async def create_cost_center(db: AsyncSession, *, code: str, name: str, owner_id=None) -> CostCenter:
    code = code.strip()
    if await get_cost_center_by_code(db, code) is not None:
        raise ProblemException(409, "Conflict", f"Cost center code '{code}' already exists.")
    cc = CostCenter(code=code, name=name, owner_id=owner_id)
    db.add(cc)
    await db.flush()
    return cc


async def create_gl_account(db: AsyncSession, *, code: str, name: str) -> GLAccount:
    code = code.strip()
    if await get_gl_account_by_code(db, code) is not None:
        raise ProblemException(409, "Conflict", f"GL account code '{code}' already exists.")
    gl = GLAccount(code=code, name=name)
    db.add(gl)
    await db.flush()
    return gl


async def _list(db, model, active, page, page_size):
    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    if active is not None:
        stmt = stmt.where(model.is_active.is_(active))
        count_stmt = count_stmt.where(model.is_active.is_(active))
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(stmt.order_by(model.code).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return list(rows), total


async def list_cost_centers(db, *, active, page, page_size):
    return await _list(db, CostCenter, active, page, page_size)


async def list_gl_accounts(db, *, active, page, page_size):
    return await _list(db, GLAccount, active, page, page_size)


async def update_cost_center(db, cc: CostCenter, *, name=None, owner_id=_UNSET) -> CostCenter:
    if name is not None:
        cc.name = name
    if owner_id is not _UNSET:
        cc.owner_id = owner_id
    await db.flush()
    return cc


async def update_gl_account(db, gl: GLAccount, *, name=None) -> GLAccount:
    if name is not None:
        gl.name = name
    await db.flush()
    return gl


async def set_cost_center_active(db, cc: CostCenter, active: bool) -> CostCenter:
    cc.is_active = active
    await db.flush()
    return cc


async def set_gl_account_active(db, gl: GLAccount, active: bool) -> GLAccount:
    gl.is_active = active
    await db.flush()
    return gl


async def is_in_use(db: AsyncSession, kind: str, obj_id: uuid.UUID) -> bool:
    # Slice 1: no tables reference cost centers / GL accounts yet.
    # Slice 3 (PO) will register po / po_line reference checks here.
    return False
