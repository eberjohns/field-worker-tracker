import socket
from collections.abc import AsyncGenerator
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import async_session_factory, engine


def is_db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


db_required = pytest.mark.skipif(
    not is_db_available(),
    reason="Database integration tests require PostgreSQL running on localhost:5432",
)


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")
    async with async_session_factory() as session:
        yield session


# Payroll settings seeded by migration 0003. Payroll has no hard-coded fallbacks (DEC-58 /
# Batch 5.3b), and the "reset database" test wipes company settings, so restore them per test.
_SEEDED_PAYROLL_SETTINGS = {
    "standard_ot_divisor_hours": 208,
    "ot1_multiplier": 1.25,
    "ot2_multiplier": 1.5,
    "hr_overhead_rate": 0.05,
    "provision_visa": 132,
    "provision_air_ticket": 65,
    "provision_uniform": 30,
    "provision_accommodation": 550,
    "provision_medical": 65,
}


@pytest.fixture(autouse=True)
async def seeded_payroll_settings() -> None:
    if not is_db_available():
        return
    from fw.modules.settings import CompanySettingValue

    async with async_session_factory() as session:
        present = set(
            (
                await session.execute(
                    select(CompanySettingValue.setting_key).where(
                        CompanySettingValue.setting_key.in_(list(_SEEDED_PAYROLL_SETTINGS)),
                        CompanySettingValue.country.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for key, value in _SEEDED_PAYROLL_SETTINGS.items():
            if key not in present:
                session.add(
                    CompanySettingValue(
                        setting_key=key, country=None, value=value, effective_from=date(2020, 1, 1)
                    )
                )
        await session.commit()
