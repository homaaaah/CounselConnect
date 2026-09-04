"""FastAPI application factory for the CounselConnect modular monolith.

All domain modules run inside this ONE application (no microservices).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import install_error_handlers
from app.modules_router import api_router


def create_app() -> FastAPI:
    """Construct the single deployable FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="CounselConnect API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
