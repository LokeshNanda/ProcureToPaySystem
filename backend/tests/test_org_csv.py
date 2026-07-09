import pytest

from app.modules.org import csv_import, service


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
