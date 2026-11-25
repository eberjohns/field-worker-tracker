import gc
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware

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
from fw.core.perf import perf_timing_active


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL)
    from fw.modules.attendance import register_attendance_listeners
    from fw.modules.events.live_publisher import live_position_broadcaster
    from fw.modules.jobs import register_jobs_listeners
    from fw.modules.notifications import register_notification_handlers
    from fw.modules.reports import register_reports_listeners
    from fw.modules.sync import register_sync_listeners

    register_sync_listeners()
    register_attendance_listeners()
    register_jobs_listeners()
    register_notification_handlers()
    register_reports_listeners()
    await live_position_broadcaster.start_listener()
    # Everything loaded so far (modules, models, routes: about 265,000 objects) lives as long as
    # the process. Freezing it keeps the garbage collector from scanning it on every full
    # collection; during a payroll draft that cut the longest pause from 425 to 270 ms
    # (Batch 9 step 4).
    gc.collect()
    gc.freeze()
    try:
        yield
    finally:
        from fw.modules.tasks import shutdown_background_jobs

        await shutdown_background_jobs()
        await live_position_broadcaster.stop_listener()


GZIP_MINIMUM_SIZE = 1024
GZIP_EXCLUDED_CONTENT_TYPES = (
    *DEFAULT_EXCLUDED_CONTENT_TYPES,  # includes text/event-stream
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)


def create_app() -> FastAPI:
    settings = get_settings()
    from fw.modules.attendance import register_attendance_listeners
    from fw.modules.jobs import register_jobs_listeners
    from fw.modules.notifications import register_notification_handlers
    from fw.modules.reports import register_reports_listeners
    from fw.modules.sync import register_sync_listeners

    register_sync_listeners()
    register_attendance_listeners()
    register_jobs_listeners()
    register_notification_handlers()
    register_reports_listeners()

    app = FastAPI(
        title="Field Worker Tracker API",
        version="0.1.0",
        description="Backend API for Field Worker Tracker (FWT)",
        lifespan=lifespan,
    )

    timing = perf_timing_active(settings)
    if settings.PERF_TIMING_ENABLED and not timing:
        structlog.get_logger("fw.perf").warning("perf_timing_ignored", app_env=settings.APP_ENV)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=(
            r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if settings.APP_ENV == "local" else None
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Server-Timing"] if timing else [],
    )

    # Compress responses of 1 KB or more for clients that accept gzip (Batch 9 step 2).
    # The live SSE stream (text/event-stream) and already-compressed files are left alone.
    app.add_middleware(
        GZipMiddleware,
        minimum_size=GZIP_MINIMUM_SIZE,
        compresslevel=6,
        exclude_content_types=GZIP_EXCLUDED_CONTENT_TYPES,
    )

    # Exception handlers (RFC 7807 problem details)
    app.add_exception_handler(ProblemDetailsException, problem_exception_handler)  # type: ignore
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register routers
    app.include_router(health_router)
    app.include_router(api_v1_router)

    if timing:
        # Added last, so it is the outermost middleware and times everything.
        from fw.core.db import engine
        from fw.core.perf import install_perf_timing

        install_perf_timing(app, engine, slow_ms=settings.PERF_SLOW_QUERY_MS)

    return app


app = create_app()
