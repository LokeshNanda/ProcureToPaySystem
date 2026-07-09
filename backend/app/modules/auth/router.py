from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditWriter
from app.core.db import get_session
from app.core.errors import ProblemException
from app.core.mail import send_email
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, PasswordResetConfirm, PasswordResetRequest, RefreshRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])
_audit = AuditWriter()


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_session)) -> TokenPair:
    user = await service.authenticate(db, payload.email, payload.password)
    if user is None:
        raise ProblemException(401, "Invalid Credentials", "Email or password is incorrect.")
    tokens = await service.issue_tokens(db, user)
    await _audit.record(db, action="auth.login", object_type="user", object_id=str(user.id))
    await db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_session)) -> TokenPair:
    tokens = await service.rotate(db, payload.refresh_token)
    await db.commit()
    return tokens


@router.post("/logout", status_code=204)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_session)) -> None:
    await service.revoke(db, payload.refresh_token)
    await _audit.record(db, action="auth.logout", object_type="session")
    await db.commit()


@router.post("/password-reset", status_code=202)
async def password_reset(payload: PasswordResetRequest, db: AsyncSession = Depends(get_session)) -> dict:
    raw = await service.begin_password_reset(db, payload.email)
    if raw is not None:
        send_email(payload.email, "Password reset", f"Reset token: {raw}")
        await _audit.record(db, action="auth.password_reset_requested", object_type="user")
    await db.commit()
    return {"status": "accepted"}


@router.post("/password-reset/confirm", status_code=204)
async def password_reset_confirm(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_session)) -> None:
    await service.confirm_password_reset(db, payload.token, payload.new_password)
    await _audit.record(db, action="auth.password_reset_confirmed", object_type="user")
    await db.commit()
