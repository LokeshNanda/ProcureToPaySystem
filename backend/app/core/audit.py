from contextvars import ContextVar
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.models.base import Base, UUIDAuditMixin

_actor: ContextVar[str | None] = ContextVar("audit_actor", default=None)
_ip: ContextVar[str | None] = ContextVar("audit_ip", default=None)


def set_audit_context(actor_id: str | None, ip: str | None) -> None:
    _actor.set(actor_id)
    _ip.set(ip)


def set_audit_actor(actor_id: str | None) -> None:
    _actor.set(actor_id)


def get_audit_context() -> tuple[str | None, str | None]:
    return _actor.get(), _ip.get()


class AuditLog(UUIDAuditMixin, Base):
    __tablename__ = "audit_log"
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditWriter:
    async def record(
        self,
        db: AsyncSession,
        *,
        action: str,
        object_type: str,
        object_id: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> AuditLog:
        actor_id, ip = get_audit_context()
        entry = AuditLog(
            actor_id=actor_id, action=action, object_type=object_type,
            object_id=object_id, before=before, after=after, ip=ip,
            at=datetime.now(tz=timezone.utc),
        )
        db.add(entry)
        await db.flush()
        return entry


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else None
        set_audit_context(actor_id=None, ip=client_ip)
        return await call_next(request)
