import pytest

from app.worker import example_task


@pytest.mark.asyncio
async def test_example_task_is_idempotent_echo():
    out1 = await example_task({}, {"id": "abc"})
    out2 = await example_task({}, {"id": "abc"})
    assert out1 == out2 == {"processed": "abc"}
