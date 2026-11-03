from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.settings.models import CompanySettingValue


class SettingsService:
    @staticmethod
    async def get_setting(
        session: AsyncSession,
        key: str,
        country: str | None = None,
        as_of: date | None = None,
        default: Any = None,
    ) -> Any:
        """Resolve effective-dated company setting value for (key, country, date)."""
        target_date = as_of or datetime.now(UTC).date()

        query = (
            select(CompanySettingValue)
            .where(
                CompanySettingValue.setting_key == key,
                CompanySettingValue.effective_from <= target_date,
                or_(
                    CompanySettingValue.effective_to.is_(None),
                    CompanySettingValue.effective_to >= target_date,
                ),
            )
            .order_by(
                CompanySettingValue.country.desc().nulls_last(),
                CompanySettingValue.effective_from.desc(),
            )
        )
        if country:
            query = query.where(
                or_(
                    CompanySettingValue.country == country,
                    CompanySettingValue.country.is_(None),
                )
            )
        else:
            query = query.where(CompanySettingValue.country.is_(None))

        res = await session.execute(query)
        setting = res.scalars().first()
        if setting:
            return setting.value
        return default

    @staticmethod
    async def set_setting(
        session: AsyncSession,
        key: str,
        value: Any,
        country: str | None = None,
        effective_from: date | None = None,
        unit: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> CompanySettingValue:
        """Insert a new effective-dated setting row and close the previous row."""
        eff_from = effective_from or datetime.now(UTC).date()

        # Close existing active row if any
        query = select(CompanySettingValue).where(
            CompanySettingValue.setting_key == key,
            CompanySettingValue.country == country,
            CompanySettingValue.effective_to.is_(None),
        )
        res = await session.execute(query)
        prev = res.scalar_one_or_none()
        if prev and prev.effective_from < eff_from:
            prev.effective_to = eff_from

        row = CompanySettingValue(
            setting_key=key,
            country=country,
            value=value,
            unit=unit,
            effective_from=eff_from,
            created_by_user_id=created_by_user_id,
        )
        session.add(row)
        await session.flush()
        return row
