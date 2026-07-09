import uuid

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import set_audit_actor
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.security import decode_token
from app.modules.users.models import User


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ProblemException(401, "Not Authenticated", "Missing bearer token.")
    return header.removeprefix("Bearer ").strip()


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_session)
) -> User:
    claims = decode_token(_bearer(request))
    if claims.get("type") != "access":
        raise ProblemException(401, "Invalid Token", "Not an access token.")
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise ProblemException(401, "Invalid Token", "Malformed subject claim.") from exc
    user = await db.get(User, user_id)
    if user is None:
        raise ProblemException(401, "Invalid Token", "User not found.")
    set_audit_actor(str(user.id))
    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise ProblemException(403, "Inactive User", "This account is deactivated.")
    return user
