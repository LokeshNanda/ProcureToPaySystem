import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ProblemException
from app.core.security import create_access_token, create_refresh_token, decode_token, verify_password
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import TokenPair
from app.modules.users.models import User
from app.modules.users.service import get_by_email


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def issue_tokens(db: AsyncSession, user: User) -> TokenPair:
    jti = uuid.uuid4().hex
    db.add(RefreshToken(
        user_id=user.id, jti=jti,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    ))
    await db.flush()
    roles = [r.name for r in user.roles]
    return TokenPair(
        access_token=create_access_token(sub=str(user.id), roles=roles, jti=uuid.uuid4().hex),
        refresh_token=create_refresh_token(sub=str(user.id), jti=jti),
    )


async def _valid_refresh_row(db: AsyncSession, token: str) -> tuple[User, RefreshToken]:
    claims = decode_token(token)
    if claims.get("type") != "refresh":
        raise ProblemException(401, "Invalid Token", "Not a refresh token.")
    row = (await db.execute(select(RefreshToken).where(RefreshToken.jti == claims["jti"]))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise ProblemException(401, "Invalid Token", "Refresh token revoked or unknown.")
    user = await db.get(User, uuid.UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise ProblemException(401, "Invalid Token", "User not found or inactive.")
    return user, row


async def rotate(db: AsyncSession, token: str) -> TokenPair:
    user, row = await _valid_refresh_row(db, token)
    row.revoked_at = datetime.now(tz=timezone.utc)
    await db.flush()
    return await issue_tokens(db, user)


async def revoke(db: AsyncSession, token: str) -> None:
    _, row = await _valid_refresh_row(db, token)
    row.revoked_at = datetime.now(tz=timezone.utc)
    await db.flush()
