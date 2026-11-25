"""Our own Google Maps usage counter (Batch 8, ADR-033).

The browser reports each map it creates and each Search press. Counts are kept per environment
(``APP_ENV``) and calendar month, so Admin can see them in Settings > System next to a soft limit
before Google's daily quotas cut the map off.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.settings.models import MapUsageCounter
from fw.modules.settings.service import SettingsService

MapUsageKind = Literal["MAP_LOAD", "GEOCODE"]

SOFT_LIMIT_KEYS: dict[str, str] = {
    "MAP_LOAD": "map_loads_soft_limit_month",
    "GEOCODE": "geocodes_soft_limit_month",
}
# 80 % of the starting daily quotas (300 map loads, 100 geocodes) over 30 days (runbook 08).
SOFT_LIMIT_DEFAULTS: dict[str, int] = {"MAP_LOAD": 7200, "GEOCODE": 2400}


class MapUsageIncrement(BaseModel):
    kind: MapUsageKind
    count: int = Field(default=1, ge=1, le=50)


class MapUsageMonth(BaseModel):
    month: str  # YYYY-MM
    map_loads: int
    geocodes: int


class MapUsageSummary(BaseModel):
    environment: str
    months: list[MapUsageMonth]
    soft_limits: dict[str, int]
    warnings: list[str]


def month_start(today: date) -> date:
    return today.replace(day=1)


def _shift_month(d: date, back: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 - back, 12)
    return date(y, m + 1, 1)


class MapUsageService:
    @staticmethod
    async def record(
        session: AsyncSession,
        environment: str,
        kind: str,
        count: int = 1,
        today: date | None = None,
    ) -> None:
        """Adds ``count`` to this month's counter (one upsert, safe under concurrency)."""
        now = datetime.now(UTC)
        stmt = insert(MapUsageCounter).values(
            environment=environment,
            month=month_start(today or now.date()),
            kind=kind,
            count=count,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_map_usage_env_month_kind",
            set_={"count": MapUsageCounter.count + count, "updated_at": now},
        )
        await session.execute(stmt)

    @staticmethod
    async def summary(
        session: AsyncSession, environment: str, months: int = 6, today: date | None = None
    ) -> MapUsageSummary:
        current = month_start(today or datetime.now(UTC).date())
        first = _shift_month(current, months - 1)
        rows = (
            await session.execute(
                select(MapUsageCounter.month, MapUsageCounter.kind, MapUsageCounter.count).where(
                    MapUsageCounter.environment == environment,
                    MapUsageCounter.month >= first,
                )
            )
        ).all()
        counts: dict[tuple[date, str], int] = {(month, kind): n for month, kind, n in rows}
        result = [
            MapUsageMonth(
                month=m.strftime("%Y-%m"),
                map_loads=counts.get((m, "MAP_LOAD"), 0),
                geocodes=counts.get((m, "GEOCODE"), 0),
            )
            for m in (_shift_month(current, i) for i in range(months))
        ]
        limits: dict[str, int] = {}
        for kind, key in SOFT_LIMIT_KEYS.items():
            value = await SettingsService.get_setting(
                session, key, default=SOFT_LIMIT_DEFAULTS[kind]
            )
            limits[kind] = int(value)
        this_month = result[0]
        warnings: list[str] = []
        if this_month.map_loads >= limits["MAP_LOAD"]:
            warnings.append(
                f"Map loads this month ({this_month.map_loads}) reached the soft limit ({limits['MAP_LOAD']})."
            )
        if this_month.geocodes >= limits["GEOCODE"]:
            warnings.append(
                f"Place searches this month ({this_month.geocodes}) reached the soft limit ({limits['GEOCODE']})."
            )
        return MapUsageSummary(
            environment=environment, months=result, soft_limits=limits, warnings=warnings
        )
