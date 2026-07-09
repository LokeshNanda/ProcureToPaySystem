from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-only-insecure-change-me-in-production-0123456789"
_INSECURE_SECRET_MARKERS = ("change-me", "insecure")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://openp2p:openp2p@localhost:5432/openp2p"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = DEFAULT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    secret_encryption_key: str = ""
    storage_backend: str = "local"
    storage_local_root: str = "./storage_data"
    frontend_origin: str = "http://localhost:5173"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin"


def is_insecure_secret_key(secret_key: str) -> bool:
    """Return True if a SECRET_KEY is a known-insecure default/placeholder value."""
    if secret_key == DEFAULT_SECRET_KEY:
        return True
    lowered = secret_key.lower()
    return any(marker in lowered for marker in _INSECURE_SECRET_MARKERS)


def assert_secure_config(settings: "Settings") -> None:
    """Fail closed: refuse to run with an insecure default SECRET_KEY in production."""
    if settings.environment == "production" and is_insecure_secret_key(settings.secret_key):
        raise RuntimeError(
            "Refusing to start: SECRET_KEY is a known-insecure default/placeholder value "
            "while ENVIRONMENT=production. Set a real, unique SECRET_KEY."
        )


settings = Settings()
