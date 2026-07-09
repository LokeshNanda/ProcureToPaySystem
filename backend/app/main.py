from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.audit import AuditMiddleware
from app.core.config import assert_secure_config, settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging
from app.health.router import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.org.router import cost_center_router, gl_account_router
from app.modules.users.router import router as users_router


def create_app() -> FastAPI:
    assert_secure_config(settings)
    setup_logging()
    app = FastAPI(title="OpenP2P", version="0.0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(cost_center_router, prefix="/api/v1")
    app.include_router(gl_account_router, prefix="/api/v1")
    return app


app = create_app()
