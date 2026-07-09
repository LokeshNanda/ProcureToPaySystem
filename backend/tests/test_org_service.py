import pytest

from app.core.errors import ProblemException
from app.modules.org import service


@pytest.mark.asyncio
async def test_create_and_get_cost_center(db_session):
    cc = await service.create_cost_center(db_session, code="4200", name="Marketing")
    assert cc.code == "4200" and cc.is_active is True
    again = await service.get_cost_center_by_code(db_session, "4200")
    assert again.id == cc.id


@pytest.mark.asyncio
async def test_duplicate_cost_center_code_conflicts(db_session):
    await service.create_cost_center(db_session, code="4200", name="A")
    with pytest.raises(ProblemException) as exc:
        await service.create_cost_center(db_session, code="4200", name="B")
    assert exc.value.status == 409


@pytest.mark.asyncio
async def test_list_active_filter_and_deactivate(db_session):
    await service.create_cost_center(db_session, code="1", name="A")
    b = await service.create_cost_center(db_session, code="2", name="B")
    await service.set_cost_center_active(db_session, b, False)
    active, total_active = await service.list_cost_centers(db_session, active=True, page=1, page_size=25)
    assert {c.code for c in active} == {"1"} and total_active == 1
    allrows, total_all = await service.list_cost_centers(db_session, active=None, page=1, page_size=25)
    assert total_all == 2


@pytest.mark.asyncio
async def test_gl_account_crud(db_session):
    gl = await service.create_gl_account(db_session, code="6000", name="Office Supplies")
    updated = await service.update_gl_account(db_session, gl, name="Supplies")
    assert updated.name == "Supplies"
    with pytest.raises(ProblemException) as exc:
        await service.create_gl_account(db_session, code="6000", name="dup")
    assert exc.value.status == 409


@pytest.mark.asyncio
async def test_is_in_use_returns_false(db_session):
    cc = await service.create_cost_center(db_session, code="9", name="X")
    assert await service.is_in_use(db_session, "cost_center", cc.id) is False
