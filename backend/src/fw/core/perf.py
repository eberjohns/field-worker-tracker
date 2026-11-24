"""Per-request timing for measuring speed (Batch 9 step 1): a Server-Timing header and one log line.

Dev and staging only. ``create_app()`` installs it when ``PERF_TIMING_ENABLED`` is set and
``APP_ENV`` is not production. Per request it counts the SQL statements and their time, the most
repeated statement (a sign of queries in a loop) and the slow ones. SQL is logged as the statement
text only, never the parameter values, so no data reaches the logs. Paths are logged as the route
template (``/api/v1/worksites/{worksite_id}``), never with IDs.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import event
from starlette.datastructures import MutableHeaders

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from fw.core.config import Settings

logger = structlog.get_logger("fw.perf")

# Long-lived streams: the duration is the stream's lifetime, not a page cost. Exact paths, so
# /api/v1/live/stream-ticket is still timed.
SKIP_PATHS = frozenset({"/api/v1/live/stream"})
MAX_SLOW_LOGGED = 5
SQL_PREVIEW_CHARS = 300
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_START_KEY = "fw_perf_start"


@dataclass
class RequestStats:
    """What one request did in the database."""

    queries: int = 0
    db_seconds: float = 0.0
    statements: Counter[str] = field(default_factory=Counter)
    slow: list[tuple[float, str]] = field(default_factory=list)

    @property
    def repeated_max(self) -> int:
        """How often the most repeated statement ran (1 = no repeats)."""
        return max(self.statements.values(), default=0)

    @property
    def db_ms(self) -> float:
        return self.db_seconds * 1000


_current: ContextVar[RequestStats | None] = ContextVar("fw_perf_stats", default=None)
_slow_ms: float = 100.0


def current_stats() -> RequestStats | None:
    return _current.get()


def perf_timing_active(settings: Settings) -> bool:
    """On only when asked for, and never in production."""
    return bool(settings.PERF_TIMING_ENABLED) and settings.APP_ENV != "production"


def _before_cursor_execute(
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    if _current.get() is not None:
        conn.info.setdefault(_START_KEY, []).append(time.perf_counter())


def _after_cursor_execute(
    conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
) -> None:
    stats = _current.get()
    starts = conn.info.get(_START_KEY)
    if stats is None or not starts:
        return
    elapsed = time.perf_counter() - starts.pop()
    stats.queries += 1
    stats.db_seconds += elapsed
    stats.statements[statement] += 1
    if elapsed * 1000 >= _slow_ms:
        stats.slow.append((elapsed * 1000, statement))


def _handle_error(exception_context: Any) -> None:
    # A failed statement never reaches after_cursor_execute; drop its start time.
    conn = getattr(exception_context, "connection", None)
    if conn is not None and conn.info.get(_START_KEY):
        conn.info[_START_KEY].pop()


def install_query_listeners(engine: AsyncEngine, slow_ms: float) -> None:
    """Count statements on this engine (idempotent). They only count inside a timed request."""
    global _slow_ms
    _slow_ms = float(slow_ms)
    sync_engine = engine.sync_engine
    for name, fn in (
        ("before_cursor_execute", _before_cursor_execute),
        ("after_cursor_execute", _after_cursor_execute),
        ("handle_error", _handle_error),
    ):
        if not event.contains(sync_engine, name, fn):
            event.listen(sync_engine, name, fn)


def route_template(scope: Scope) -> str:
    """The matched route's template, else the path with path parameters and UUIDs replaced."""
    route = scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        # Newer FastAPI keeps the route without its router prefix ("/reports/{key}"): put back the
        # part of the real path in front of it ("/api/v1").
        path = str(scope.get("path", ""))
        static = template.split("{", 1)[0]
        if static and not path.startswith(static):
            p, t = path.strip("/").split("/"), template.strip("/").split("/")
            if len(p) > len(t):
                return "/" + "/".join(p[: len(p) - len(t)] + t)
        return template
    names = {str(value): name for name, value in (scope.get("path_params") or {}).items()}
    segments = _UUID.sub("{id}", str(scope.get("path", ""))).split("/")
    return "/".join("{" + names[s] + "}" if s in names else s for s in segments)


def is_timed(path: str) -> bool:
    return path.rstrip("/") not in SKIP_PATHS


def server_timing(app_ms: float, stats: RequestStats) -> str:
    return (
        f'app;dur={app_ms:.1f};desc="app", '
        f'db;dur={stats.db_ms:.1f};desc="{stats.queries} queries", '
        f'dbrepeat;desc="{stats.repeated_max} max repeats"'
    )


def _preview(statement: str) -> str:
    return " ".join(statement.split())[:SQL_PREVIEW_CHARS]


class RequestTimingMiddleware:
    """Pure ASGI middleware (outermost): times the request and writes ``request_timing``.

    The header is added when the response starts. For a streamed body (file downloads) it holds
    the time until the first byte; the log line holds the full duration.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not is_timed(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        stats = RequestStats()
        token = _current.set(stats)
        start = time.perf_counter()
        status = 500

        async def send_with_timing(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers.append(
                    "Server-Timing", server_timing((time.perf_counter() - start) * 1000, stats)
                )
                headers.append("Timing-Allow-Origin", "*")
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            _current.reset(token)
            slowest = sorted(stats.slow, reverse=True)[:MAX_SLOW_LOGGED]
            logger.info(
                "request_timing",
                method=scope.get("method"),
                route=route_template(scope),
                status=status,
                duration_ms=round((time.perf_counter() - start) * 1000, 1),
                db_queries=stats.queries,
                db_ms=round(stats.db_ms, 1),
                repeated_max=stats.repeated_max,
                slow_queries=[{"ms": round(ms, 1), "sql": _preview(sql)} for ms, sql in slowest],
            )


def install_perf_timing(app: FastAPI, engine: AsyncEngine, slow_ms: float) -> None:
    """Add the middleware (outermost, so it times everything) and the query listeners."""
    install_query_listeners(engine, slow_ms)
    app.add_middleware(RequestTimingMiddleware)
