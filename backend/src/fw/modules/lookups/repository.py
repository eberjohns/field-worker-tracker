from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.lookups.models import LookupValue


class LookupRepository:
    @staticmethod
    async def list_values(
        session: AsyncSession, list_key: str, include_inactive: bool = True
    ) -> list[LookupValue]:
        stmt = select(LookupValue).where(LookupValue.list_key == list_key)
        if not include_inactive:
            stmt = stmt.where(LookupValue.is_active.is_(True))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def list_all(session: AsyncSession, list_keys: Iterable[str]) -> list[LookupValue]:
        stmt = select(LookupValue).where(LookupValue.list_key.in_(list(list_keys)))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get(session: AsyncSession, list_key: str, value_id: UUID) -> LookupValue | None:
        row = await session.get(LookupValue, value_id)
        return row if row is not None and row.list_key == list_key else None

    @staticmethod
    async def delete_all(session: AsyncSession) -> None:
        await session.execute(delete(LookupValue))
