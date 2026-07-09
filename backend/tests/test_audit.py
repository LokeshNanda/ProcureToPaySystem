import pytest
from sqlalchemy import select

from app.core.audit import AuditLog, AuditWriter, set_audit_context


@pytest.mark.asyncio
async def test_audit_writer_records_entry(db_session):
    set_audit_context(actor_id="actor-1", ip="1.2.3.4")
    writer = AuditWriter()
    await writer.record(
        db_session, action="user.create", object_type="user",
        object_id="u1", before=None, after={"email": "x@y.com"},
    )
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "user.create"
    assert rows[0].actor_id == "actor-1"
    assert rows[0].ip == "1.2.3.4"
    assert rows[0].after == {"email": "x@y.com"}
