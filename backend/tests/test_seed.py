import pytest
from sqlalchemy import func, select

from app.core.rbac import ALL_ROLES
from app.modules.users.models import Role, User
from app.seed import seed_with_session


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    await seed_with_session(db_session)
    await seed_with_session(db_session)  # second run must not duplicate
    roles = (await db_session.execute(select(func.count()).select_from(Role))).scalar_one()
    admins = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert roles == len(ALL_ROLES)
    assert admins == 1
