from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings
from app.core.errors import ProblemException

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _ph.verify(hashed, password)
    except Argon2Error:
        return False


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(*, sub: str, roles: list[str], jti: str) -> str:
    exp = _now() + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {"sub": sub, "roles": roles, "jti": jti, "type": "access", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, sub: str, jti: str) -> str:
    exp = _now() + timedelta(days=settings.refresh_token_ttl_days)
    payload = {"sub": sub, "jti": jti, "type": "refresh", "exp": exp}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise ProblemException(401, "Token Expired", "The token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise ProblemException(401, "Invalid Token", "The token is invalid.") from exc
