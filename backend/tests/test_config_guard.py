import pytest

from app.core.config import DEFAULT_SECRET_KEY, Settings, assert_secure_config


def _settings(**overrides) -> Settings:
    defaults = {"environment": "dev", "secret_key": DEFAULT_SECRET_KEY}
    defaults.update(overrides)
    return Settings(**defaults)


def test_production_with_default_secret_raises():
    with pytest.raises(RuntimeError):
        assert_secure_config(_settings(environment="production", secret_key=DEFAULT_SECRET_KEY))


def test_production_with_change_me_marker_raises():
    with pytest.raises(RuntimeError):
        assert_secure_config(_settings(environment="production", secret_key="please-change-me-now"))


def test_production_with_insecure_marker_raises():
    with pytest.raises(RuntimeError):
        assert_secure_config(_settings(environment="production", secret_key="totally-insecure-value"))


def test_dev_with_insecure_default_does_not_raise():
    assert_secure_config(_settings(environment="dev", secret_key=DEFAULT_SECRET_KEY))


def test_test_env_with_insecure_default_does_not_raise():
    assert_secure_config(_settings(environment="test", secret_key=DEFAULT_SECRET_KEY))


def test_production_with_strong_secret_does_not_raise():
    strong_key = "9f3c1a7e6b2d4f80a1c5e9b7d3f2a6c8e0b4d7f1a3c5e8b2d4f6a9c1e3b5d7f9"
    assert_secure_config(_settings(environment="production", secret_key=strong_key))
