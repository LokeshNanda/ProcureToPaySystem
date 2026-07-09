import logging

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger("worker")


async def example_task(ctx: dict, payload: dict) -> dict:
    # Idempotent: derives output purely from input; safe to retry.
    logger.info("example_task", extra={"payload_id": payload.get("id")})
    return {"processed": payload["id"]}


async def _on_startup(ctx: dict) -> None:
    setup_logging()
    logger.info("worker.startup")


async def _on_shutdown(ctx: dict) -> None:
    logger.info("worker.shutdown")


class WorkerSettings:
    functions = [example_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = _on_startup
    on_shutdown = _on_shutdown
