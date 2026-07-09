import pytest

from app.core.storage import LocalStorage


@pytest.mark.asyncio
async def test_local_storage_round_trip(tmp_path):
    store = LocalStorage(str(tmp_path))
    key = store.generate_key(".txt")
    await store.save(key, b"hello")
    assert await store.open(key) == b"hello"
    await store.delete(key)


def test_generate_key_is_random_not_filename():
    store = LocalStorage("/tmp")
    k1 = store.generate_key(".pdf")
    k2 = store.generate_key(".pdf")
    assert k1 != k2 and k1.endswith(".pdf")
