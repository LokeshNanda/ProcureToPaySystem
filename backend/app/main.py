from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging
from app.health.router import router as health_router


def create_app() -> FastAPI:
    setup_logging()
    app = FastAPI(title="OpenP2P", version="0.0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
