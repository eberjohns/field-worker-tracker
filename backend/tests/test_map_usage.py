"""Google Maps usage counter (Batch 8, ADR-033).

- Increments add up per environment, month and kind in one row each.
- The summary lists the last months (zeros included) and warns at the soft limit.
- Any signed-in user can report usage; only Admin can read it; bad kinds are refused.
"""

from datetime import date
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import get_settings
from fw.main import app
from fw.modules.settings import MapUsageCounter, MapUsageService
from tests.test_payroll_api import _create_test_employee, _create_test_user


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_record_adds_up_and_summary_lists_months(db_session: AsyncSession):
    env = f"t{uuid4().hex[:8]}"
    today = date(2026, 11, 20)
    try:
        await MapUsageService.record(db_session, env, "MAP_LOAD", 1, today=today)
        await MapUsageService.record(db_session, env, "MAP_LOAD", 2, today=today)
        await MapUsageService.record(db_session, env, "GEOCODE", 1, today=today)
        await MapUsageService.record(db_session, env, "MAP_LOAD", 5, today=date(2026, 9, 3))
        await db_session.commit()

        rows = (
            (
                await db_session.execute(
                    select(MapUsageCounter).where(MapUsageCounter.environment == env)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 3

        s = await MapUsageService.summary(db_session, env, months=3, today=today)
        assert [m.month for m in s.months] == ["2026-11", "2026-10", "2026-09"]
        assert (s.months[0].map_loads, s.months[0].geocodes) == (3, 1)
        assert (s.months[1].map_loads, s.months[1].geocodes) == (0, 0)
        assert s.months[2].map_loads == 5
        assert s.soft_limits["MAP_LOAD"] > 0 and s.soft_limits["GEOCODE"] > 0
        assert s.warnings == []
    finally:
        await db_session.execute(delete(MapUsageCounter).where(MapUsageCounter.environment == env))
        await db_session.commit()


@pytest.mark.asyncio
async def test_summary_warns_at_the_soft_limit(db_session: AsyncSession):
    env = f"t{uuid4().hex[:8]}"
    today = date(2026, 11, 20)
    try:
        limits = (await MapUsageService.summary(db_session, env, months=1, today=today)).soft_limits
        await MapUsageService.record(db_session, env, "GEOCODE", limits["GEOCODE"], today=today)
        await db_session.commit()
        s = await MapUsageService.summary(db_session, env, months=1, today=today)
        assert len(s.warnings) == 1
        assert "Place searches" in s.warnings[0]
    finally:
        await db_session.execute(delete(MapUsageCounter).where(MapUsageCounter.environment == env))
        await db_session.commit()


@pytest.mark.asyncio
async def test_api_any_user_reports_only_admin_reads(db_session: AsyncSession):
    env = get_settings().APP_ENV
    emp = await _create_test_employee(db_session, f"MU_{uuid4().hex[:6]}", "Map User")
    _, sup_token = await _create_test_user(db_session, emp, "SUPERVISOR")
    _, admin_token = await _create_test_user(db_session, None, "ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = (await client.get("/api/v1/map-usage?months=1", headers=_h(admin_token))).json()
        assert before["environment"] == env

        r = await client.post("/api/v1/map-usage", headers=_h(sup_token), json={"kind": "MAP_LOAD"})
        assert r.status_code == 204
        r = await client.post(
            "/api/v1/map-usage", headers=_h(sup_token), json={"kind": "GEOCODE", "count": 2}
        )
        assert r.status_code == 204

        after = (await client.get("/api/v1/map-usage?months=1", headers=_h(admin_token))).json()
        assert after["months"][0]["map_loads"] == before["months"][0]["map_loads"] + 1
        assert after["months"][0]["geocodes"] == before["months"][0]["geocodes"] + 2

        assert (await client.get("/api/v1/map-usage", headers=_h(sup_token))).status_code == 403
        bad = await client.post("/api/v1/map-usage", headers=_h(sup_token), json={"kind": "TILES"})
        assert bad.status_code in (400, 422)
        too_many = await client.post(
            "/api/v1/map-usage", headers=_h(sup_token), json={"kind": "MAP_LOAD", "count": 500}
        )
        assert too_many.status_code in (400, 422)
        assert (
            await client.post("/api/v1/map-usage", json={"kind": "MAP_LOAD"})
        ).status_code == 401
