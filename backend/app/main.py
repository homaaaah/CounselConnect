"""FastAPI application factory for the CounselConnect modular monolith.

All domain modules run inside this ONE application (no microservices).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import install_error_handlers
from app.modules_router import api_router
from app.shared.responses import ErrorResponse, ValidationErrorResponse


def create_app(*, run_cleanup: bool = True) -> FastAPI:
    """Construct the single deployable FastAPI application."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from app.modules.enrollment_verification.cleanup import cleanup_loop

        stop = Event()
        worker = Thread(
            target=cleanup_loop, args=(stop,), name="cor-cleanup", daemon=True
        )
        if run_cleanup:
            worker.start()
        try:
            yield
        finally:
            stop.set()
            if run_cleanup:
                await asyncio.to_thread(worker.join, 5)

    app = FastAPI(
        title="CounselConnect API",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        responses={
            422: {
                "model": ValidationErrorResponse | ErrorResponse,
                "description": "Sanitized validation or business-rule errors",
            }
        },
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
