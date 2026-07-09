import pytest


@pytest.mark.asyncio
async def test_health_liveness(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_ready(client):
    resp = await client.get("/health/ready")
    assert resp.status_code in (200, 503)
    assert "checks" in resp.json()
