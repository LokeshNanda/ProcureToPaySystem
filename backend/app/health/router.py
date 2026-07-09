import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response, db: AsyncSession = Depends(get_session)) -> dict:
    checks = {"db": False, "redis": False, "storage": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        store = get_storage()
        key = store.generate_key(".probe")
        await store.save(key, b"ok")
        await store.delete(key)
        checks["storage"] = True
    except Exception:  # noqa: BLE001
        pass
    ok = all(checks.values())
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "degraded", "checks": checks}
