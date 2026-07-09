import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemException
from app.core.rbac import ALL_ROLES
from app.core.security import hash_password
from app.modules.users.models import Role, User


def _validate_role_names(role_names: list[str]) -> None:
    for name in role_names:
        if name not in ALL_ROLES:
            raise ProblemException(400, "Invalid Role", f"Unknown role: {name}")


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
    _validate_role_names(role_names)
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
    _validate_role_names(role_names)
    user.roles = [await get_or_create_role(db, n) for n in role_names]
    await db.flush()
    return user


async def deactivate(db: AsyncSession, user: User) -> User:
    user.is_active = False
    await db.flush()
    return user


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
