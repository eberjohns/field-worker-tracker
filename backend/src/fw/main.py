from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from fw.api import api_v1_router
from fw.api.health import router as health_router
from fw.core.config import get_settings
from fw.core.errors import (
    ProblemDetailsException,
    generic_exception_handler,
    http_exception_handler,
    problem_exception_handler,
    validation_exception_handler,
)
from fw.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    from fw.modules.sync import register_sync_listeners

    register_sync_listeners()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    from fw.modules.sync import register_sync_listeners

    register_sync_listeners()

    app = FastAPI(
        title="Field Worker Tracker API",
        version="0.1.0",
        description="Backend API for Field Worker Tracker (FWT)",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=(
            r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
            if settings.APP_ENV == "local"
            else None
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers (RFC 7807 problem details)
    app.add_exception_handler(ProblemDetailsException, problem_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register routers
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


app = create_app()
