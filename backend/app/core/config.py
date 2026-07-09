from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://openp2p:openp2p@localhost:5432/openp2p"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-only-insecure-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    secret_encryption_key: str = ""
    storage_backend: str = "local"
    storage_local_root: str = "./storage_data"
    frontend_origin: str = "http://localhost:5173"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin"


settings = Settings()
