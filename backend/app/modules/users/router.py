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
