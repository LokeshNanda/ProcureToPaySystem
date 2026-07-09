import pytest

from app.modules.users import service


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_lowercases_email(db_session):
    user = await service.create_user(
        db_session, email="Alice@Example.com", full_name="Alice",
        password="pw123456", role_names=["Requester"],
    )
    assert user.email == "alice@example.com"
    assert user.password_hash != "pw123456"
    assert {r.name for r in user.roles} == {"Requester"}
    assert user.is_active is True


@pytest.mark.asyncio
async def test_set_roles_replaces_roles(db_session):
    user = await service.create_user(
        db_session, email="bob@example.com", full_name="Bob",
        password="pw123456", role_names=["Requester"],
    )
    await service.set_roles(db_session, user, ["Approver", "Receiver"])
    assert {r.name for r in user.roles} == {"Approver", "Receiver"}
