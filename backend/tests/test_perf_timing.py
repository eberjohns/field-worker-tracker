"""Speed measuring middleware (Batch 9 step 1): Server-Timing header and the request_timing log."""

import re

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from structlog.testing import capture_logs

from fw.core.config import Settings
from fw.core.db import async_session_factory, engine
from fw.core.perf import (
    RequestTimingMiddleware,
    current_stats,
    install_perf_timing,
    is_timed,
    perf_timing_active,
    route_template,
)
from fw.main import create_app
from tests.test_batch6_features import db_required


def _probe_app() -> FastAPI:
    """A bare app with one route that runs the same statement three times."""
    app = FastAPI()

    @app.get("/probe/{item_id}")
    async def probe(item_id: str) -> dict[str, str]:
        async with async_session_factory() as session:
            for _ in range(3):
                await session.execute(text("SELECT 1"))
        return {"item_id": item_id}

    install_perf_timing(app, engine, slow_ms=100)
    return app


def test_on_only_when_asked_and_never_in_production() -> None:
    assert perf_timing_active(Settings(APP_ENV="local", PERF_TIMING_ENABLED=True))
    assert perf_timing_active(Settings(APP_ENV="staging", PERF_TIMING_ENABLED=True))
    assert not perf_timing_active(Settings(APP_ENV="production", PERF_TIMING_ENABLED=True))
    assert not perf_timing_active(Settings(APP_ENV="local", PERF_TIMING_ENABLED=False))


def test_off_by_default_no_middleware() -> None:
    app = create_app()  # the test settings leave PERF_TIMING_ENABLED off
    assert all(m.cls is not RequestTimingMiddleware for m in app.user_middleware)


def test_route_template_never_has_ids() -> None:
    scope = {
        "path": "/api/v1/worksites/0b5c1f8e-1d2a-4c3b-9e8f-7a6b5c4d3e2f/items/7",
        "path_params": {"item_no": "7"},
    }
    assert route_template(scope) == "/api/v1/worksites/{id}/items/{item_no}"

    class Route:
        path = "/reports/{key}"  # FastAPI may keep the route without its router prefix

    scope = {"path": "/api/v1/reports/job-costing", "route": Route()}
    assert route_template(scope) == "/api/v1/reports/{key}"


@db_required
@pytest.mark.asyncio
async def test_header_and_log_count_the_queries() -> None:
    uuid = "0b5c1f8e-1d2a-4c3b-9e8f-7a6b5c4d3e2f"
    async with AsyncClient(transport=ASGITransport(app=_probe_app()), base_url="http://t") as c:
        with capture_logs() as logs:
            r = await c.get(f"/probe/{uuid}")
    assert r.status_code == 200
    header = r.headers["server-timing"]
    # The ContextVar reaches SQLAlchemy's async greenlet, so the statements are counted.
    assert re.search(r'db;dur=[\d.]+;desc="(\d+) queries"', header)
    queries = int(re.search(r'desc="(\d+) queries"', header).group(1))  # type: ignore[union-attr]
    assert queries >= 3
    assert re.search(r'dbrepeat;desc="\d+ max repeats"', header)
    assert r.headers["timing-allow-origin"] == "*"

    line = next(x for x in logs if x["event"] == "request_timing")
    assert line["route"] == "/probe/{item_id}"
    assert uuid not in str(line)
    assert line["status"] == 200
    assert line["db_queries"] == queries
    assert line["repeated_max"] >= 3


def test_nothing_is_collected_outside_a_request() -> None:
    assert current_stats() is None


def test_only_the_live_stream_itself_is_left_out() -> None:
    assert not is_timed("/api/v1/live/stream")
    assert not is_timed("/api/v1/live/stream/")
    assert is_timed("/api/v1/live/stream-ticket")
    assert is_timed("/api/v1/live/positions")
