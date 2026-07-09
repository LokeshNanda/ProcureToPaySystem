import pytest

from app.modules.org import csv_import, service
from app.modules.users import service as users_service


@pytest.mark.asyncio
async def test_import_cost_centers_creates_and_updates(db_session):
    await service.create_cost_center(db_session, code="4200", name="Old Name")
    csv_text = "code,name\n4200,New Name\n4300,Sales\n"
    result = await csv_import.import_cost_centers(db_session, csv_text)
    assert result["created"] == 1 and result["updated"] == 1 and result["errors"] == []
    assert (await service.get_cost_center_by_code(db_session, "4200")).name == "New Name"


@pytest.mark.asyncio
async def test_import_reports_row_errors_without_aborting_batch(db_session):
    csv_text = "code,name\n5000,Valid\n,Missing Code\n5001,Also Valid\n"
    result = await csv_import.import_gl_accounts(db_session, csv_text)
    assert result["created"] == 2
    assert len(result["errors"]) == 1 and result["errors"][0]["row"] == 3


@pytest.mark.asyncio
async def test_import_unknown_owner_email_is_row_error(db_session):
    csv_text = "code,name,owner_email\n4400,Ops,nobody@example.com\n"
    result = await csv_import.import_cost_centers(db_session, csv_text)
    assert result["created"] == 0 and len(result["errors"]) == 1
    assert "owner" in result["errors"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_import_missing_header_errors(db_session):
    result = await csv_import.import_gl_accounts(db_session, "6000,No Header Row\n")
    # 'code'/'name' header missing -> a single structural error, no rows created
    assert result["created"] == 0 and result["errors"]


@pytest.mark.asyncio
async def test_reimport_without_owner_column_preserves_owner(db_session):
    owner = await users_service.create_user(
        db_session, email="owner@example.com", full_name="Owner", password="pw123456", role_names=["Requester"]
    )
    await service.create_cost_center(db_session, code="4500", name="Facilities", owner_id=owner.id)
    # Re-import with NO owner_email column -> owner must be left unchanged.
    result = await csv_import.import_cost_centers(db_session, "code,name\n4500,Facilities Renamed\n")
    assert result["updated"] == 1 and result["errors"] == []
    cc = await service.get_cost_center_by_code(db_session, "4500")
    assert cc.name == "Facilities Renamed" and cc.owner_id == owner.id


@pytest.mark.asyncio
async def test_reimport_with_blank_owner_column_clears_owner(db_session):
    owner = await users_service.create_user(
        db_session, email="owner2@example.com", full_name="Owner", password="pw123456", role_names=["Requester"]
    )
    await service.create_cost_center(db_session, code="4600", name="Legal", owner_id=owner.id)
    # owner_email column present but blank -> owner cleared to None.
    result = await csv_import.import_cost_centers(db_session, "code,name,owner_email\n4600,Legal,\n")
    assert result["updated"] == 1 and result["errors"] == []
    cc = await service.get_cost_center_by_code(db_session, "4600")
    assert cc.owner_id is None


@pytest.mark.asyncio
async def test_reimport_without_active_column_does_not_reactivate(db_session):
    gl = await service.create_gl_account(db_session, code="7000", name="Travel")
    await service.set_gl_account_active(db_session, gl, False)
    # Re-import with NO active column -> must stay inactive.
    result = await csv_import.import_gl_accounts(db_session, "code,name\n7000,Travel Updated\n")
    assert result["updated"] == 1 and result["errors"] == []
    refreshed = await service.get_gl_account_by_code(db_session, "7000")
    assert refreshed.name == "Travel Updated" and refreshed.is_active is False


@pytest.mark.asyncio
async def test_reimport_with_truthy_active_column_reactivates(db_session):
    gl = await service.create_gl_account(db_session, code="7100", name="Meals")
    await service.set_gl_account_active(db_session, gl, False)
    result = await csv_import.import_gl_accounts(db_session, "code,name,active\n7100,Meals,true\n")
    assert result["updated"] == 1 and result["errors"] == []
    refreshed = await service.get_gl_account_by_code(db_session, "7100")
    assert refreshed.is_active is True
