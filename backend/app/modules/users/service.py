from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.models import Role, User


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
    user.roles = [await get_or_create_role(db, n) for n in role_names]
    await db.flush()
    return user


async def deactivate(db: AsyncSession, user: User) -> User:
    user.is_active = False
    await db.flush()
    return user
