import pytest

from app.core.errors import ProblemException
from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password(h, "s3cret") is True
    assert verify_password(h, "wrong") is False


def test_access_token_round_trip():
    token = create_access_token(sub="user-1", roles=["Admin"], jti="j1")
    claims = decode_token(token)
    assert claims["sub"] == "user-1"
    assert claims["roles"] == ["Admin"]
    assert claims["type"] == "access"
    assert claims["jti"] == "j1"


def test_decode_rejects_garbage():
    with pytest.raises(ProblemException):
        decode_token("not-a-jwt")
