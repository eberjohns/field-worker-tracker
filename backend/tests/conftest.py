"""Shared test setup.

Tests never use the working database (``fw_db``). Before anything from ``fw`` is imported, the
database URLs are pointed at a separate database whose name must end in ``_test`` (default
``fw_test``, or ``FW_TEST_DATABASE``). At the start of each run that database is dropped,
recreated and migrated to head, so every run starts empty.
"""

import asyncio
import os
import re
import socket
import subprocess
import sys
from collections.abc import AsyncGenerator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

TEST_DATABASE = os.environ.get("FW_TEST_DATABASE", "fw_test")
_TEST_NAME_OK = re.fullmatch(r"[a-z0-9_]+_test", TEST_DATABASE) is not None
_BACKEND_DIR = Path(__file__).resolve().parent.parent


_DEFAULT_URLS = {  # same defaults as fw.core.config.Settings
    "DATABASE_URL": "postgresql+asyncpg://fw_app:fw_secret@localhost:5432/fw_db",
    "DATABASE_MIGRATOR_URL": "postgresql+asyncpg://fw_migrator:fw_migrator_secret@localhost:5432/fw_db",
}


def _configured_url(key: str) -> str:
    """The URL the app would use: env var, else the .env files Settings reads, else the default.

    Read without importing ``fw``: importing any ``fw.core`` module creates the engine.
    """
    if os.environ.get(key):
        return os.environ[key]
    from dotenv import dotenv_values

    value = _DEFAULT_URLS[key]
    for env_file in (".env", "../.env"):  # Settings.env_file; later files win, as in pydantic
        found = dotenv_values(env_file).get(key) if Path(env_file).is_file() else None
        if found:
            value = found
    return value


def _point_settings_at_test_database() -> None:
    """Point DATABASE_URL and DATABASE_MIGRATOR_URL at the test database (env beats .env)."""
    for key in _DEFAULT_URLS:
        url = make_url(_configured_url(key)).set(database=TEST_DATABASE)
        os.environ[key] = url.render_as_string(hide_password=False)


if _TEST_NAME_OK:
    _point_settings_at_test_database()
else:
    # Never fall through to the configured database: make any connection attempt fail.
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://refused:refused@127.0.0.1:1/refused_test"
    os.environ["DATABASE_MIGRATOR_URL"] = os.environ["DATABASE_URL"]

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from fw.core.config import get_settings  # noqa: E402
from fw.core.db import async_session_factory, engine  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    if not _TEST_NAME_OK:
        pytest.exit(
            f"Refusing to run tests: database {TEST_DATABASE!r} does not end in '_test'. "
            "Tests may only use a separate test database (FW_TEST_DATABASE, default fw_test).",
            returncode=4,
        )
    for url in (engine.url, make_url(get_settings().DATABASE_MIGRATOR_URL)):
        if not (url.database or "").endswith("_test"):
            pytest.exit(
                f"Refusing to run tests: the app would use database {url.database!r}, "
                "not a '_test' database.",
                returncode=4,
            )


async def _recreate_test_database() -> None:
    settings = get_settings()
    migrator = make_url(settings.DATABASE_MIGRATOR_URL)
    app_role = make_url(settings.DATABASE_URL).username
    import asyncpg

    async def connect(database: str) -> asyncpg.Connection:
        return await asyncpg.connect(
            user=migrator.username,
            password=migrator.password,
            host=migrator.host or "127.0.0.1",
            port=migrator.port or 5432,
            database=database,
        )

    conn = await connect("postgres")
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DATABASE}"')
    finally:
        await conn.close()
    if app_role and app_role != migrator.username:
        # Same grants as infra/init-db.sql gives the app role on fw_db.
        conn = await connect(TEST_DATABASE)
        try:
            await conn.execute(f'GRANT CONNECT ON DATABASE "{TEST_DATABASE}" TO "{app_role}"')
            await conn.execute(f'GRANT USAGE ON SCHEMA public TO "{app_role}"')
            await conn.execute(
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{migrator.username}" IN SCHEMA public '
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{app_role}"'
            )
            await conn.execute(
                f'ALTER DEFAULT PRIVILEGES FOR ROLE "{migrator.username}" IN SCHEMA public '
                f'GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "{app_role}"'
            )
        finally:
            await conn.close()


@pytest.fixture(scope="session", autouse=True)
def fresh_test_database() -> None:
    """Drop, recreate and migrate the test database once per run (skipped without a server)."""
    if not is_db_available():
        return
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_recreate_test_database())
    finally:
        loop.close()
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.exit(f"alembic upgrade head failed on {TEST_DATABASE}:\n{result.stderr}", 3)


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


# Managed lists (DEC-60): grade codes and staff types that tests send through the API. Grade codes
# exist only as lines of an ACTIVE salary revision, so a test revision holds them. Its country "ZZ"
# keeps it from ever being the default AE/SA revision in budget or payroll tests. The "reset
# database" test clears revisions and lists, so make sure all of this exists before each test.
TEST_GRADE_REVISION = "TEST-GRADES"
_TEST_GRADE_CODES = (
    "G1 G1A G1B G1C G2 G2A G2B G2C G3 G3A G3B G3C G4 G4A G5 G5A G5C G6B G9A G9B G9C G10A G16A G25"
).split()


@pytest.fixture(autouse=True)
async def managed_list_values() -> None:
    if not is_db_available():
        return
    from decimal import Decimal

    from sqlalchemy import text

    from fw.modules.payroll import PayrollService, SalaryRevision, SalaryRevisionLine
    from fw.rules.lookups import SEED_STAFF_TYPES, value_key

    async with async_session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO lookup_values (id, list_key, value, value_key, source, is_active, "
                "version, created_at, updated_at) VALUES (gen_random_uuid(), "
                "'staff_grade_description', :v, :vk, 'SEED', true, 1, now(), now()) "
                "ON CONFLICT (list_key, value_key) DO NOTHING"
            ),
            [{"v": v, "vk": value_key(v)} for v in SEED_STAFF_TYPES],
        )
        rev = (
            await session.execute(
                select(SalaryRevision).where(SalaryRevision.code == TEST_GRADE_REVISION)
            )
        ).scalar_one_or_none()
        if rev is None:
            rev = SalaryRevision(
                code=TEST_GRADE_REVISION,
                name="Test grade codes (tests only)",
                country="ZZ",
                effective_from=date(2000, 1, 1),
                status="ACTIVE",
            )
            session.add(rev)
        have = {line.grade_code for line in rev.lines}
        for code in _TEST_GRADE_CODES:
            if code not in have:
                rev.lines.append(SalaryRevisionLine(grade_code=code, basic_salary=Decimal("1000")))
        await PayrollService.refresh_grade_list(session)
        await session.commit()
