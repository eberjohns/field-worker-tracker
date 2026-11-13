from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.transport.models import TransportRun, Vehicle


class TransportRepositoryPort(Protocol):
    """Port defining persistence operations for transport."""

    async def list_vehicles(
        self, session: AsyncSession, active_only: bool = True
    ) -> Sequence[Vehicle]: ...

    async def get_vehicle(self, session: AsyncSession, vehicle_id: UUID) -> Vehicle | None: ...

    async def get_run(self, session: AsyncSession, run_id: UUID) -> TransportRun | None: ...

    async def list_runs(
        self, session: AsyncSession, run_date: date, direction: str | None = None
    ) -> Sequence[TransportRun]: ...
