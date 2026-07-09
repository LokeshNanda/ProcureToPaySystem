import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.rbac import ALL_ROLES, Roles
from app.modules.users import service


async def seed_with_session(db: AsyncSession) -> None:
    for role_name in ALL_ROLES:
        await service.get_or_create_role(db, role_name)
    if await service.get_by_email(db, settings.seed_admin_email) is None:
        await service.create_user(
            db,
            email=settings.seed_admin_email,
            full_name="Administrator",
            password=settings.seed_admin_password,
            role_names=[Roles.ADMIN],
        )
    await db.flush()


async def run_seed() -> None:
    async with SessionLocal() as db:
        await seed_with_session(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(run_seed())
