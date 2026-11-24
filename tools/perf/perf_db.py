"""Point the app at the local measuring database (``fw_perf``) and (re)create it.

Same approach as ``backend/tests/conftest.py`` for ``fw_test``. ``point_at_perf_database()`` must
run before anything from ``fw`` is imported: importing ``fw.core.db`` creates the engine.

Guards (CLAUDE.md: only the local docker-compose database): the name must end in ``_perf``
(default ``fw_perf``, or ``FW_PERF_DATABASE``), both URLs must point at a local host, and
``APP_ENV`` must not be production.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

PERF_DATABASE = os.environ.get("FW_PERF_DATABASE", "fw_perf")
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"

_DEFAULTS = {  # same defaults as fw.core.config.Settings
    "DATABASE_URL": "postgresql+asyncpg://fw_app:fw_secret@localhost:5432/fw_db",
    "DATABASE_MIGRATOR_URL": "postgresql+asyncpg://fw_migrator:fw_migrator_secret@localhost:5432/fw_db",
    "APP_ENV": "local",
}


def configured(key: str) -> str:
    """The value the app would use: env var, else backend/.env then ../.env, else the default."""
    if os.environ.get(key):
        return os.environ[key]
    from dotenv import dotenv_values

    value = _DEFAULTS[key]
    for env_file in (BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"):
        found = dotenv_values(env_file).get(key) if env_file.is_file() else None
        if found:
            value = found
    return value


def problems(database: str, urls: dict[str, str], app_env: str) -> list[str]:
    """Why this target is refused (empty when it is fine)."""
    out: list[str] = []
    if re.fullmatch(r"[a-z0-9_]+_perf", database) is None:
        out.append(f"database {database!r} must be named like fw_perf (lowercase, ending in _perf)")
    for key, url in urls.items():
        host = make_url(url).host or "localhost"
        if host not in LOCAL_HOSTS:
            out.append(f"{key} points at {host!r}; only the local docker-compose database is allowed")
    if app_env == "production":
        out.append("APP_ENV is production")
    return out


def point_at_perf_database() -> dict[str, str]:
    """Set DATABASE_URL / DATABASE_MIGRATOR_URL to the perf database, or exit with the reason."""
    urls = {k: configured(k) for k in ("DATABASE_URL", "DATABASE_MIGRATOR_URL")}
    refused = problems(PERF_DATABASE, urls, configured("APP_ENV"))
    if refused:
        sys.exit("Refused: " + "; ".join(refused))
    for key, url in urls.items():
        os.environ[key] = make_url(url).set(database=PERF_DATABASE).render_as_string(hide_password=False)
    # Generated files (reports, archives) stay apart from the working database's files.
    os.environ["LOCAL_STORAGE_PATH"] = str(BACKEND_DIR / "storage" / "perf")
    os.environ["ARCHIVE_STORAGE_PATH"] = str(BACKEND_DIR / "storage" / "perf" / "archives")
    return {k: os.environ[k] for k in urls}


async def recreate_perf_database() -> None:
    """Drop, create and grant the perf database, then migrate it to head (needs the env set)."""
    import asyncpg

    migrator = make_url(os.environ["DATABASE_MIGRATOR_URL"])
    app_role = make_url(os.environ["DATABASE_URL"]).username

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
        await conn.execute(f'DROP DATABASE IF EXISTS "{PERF_DATABASE}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{PERF_DATABASE}"')
    finally:
        await conn.close()
    if app_role and app_role != migrator.username:
        conn = await connect(PERF_DATABASE)
        try:
            await conn.execute(f'GRANT CONNECT ON DATABASE "{PERF_DATABASE}" TO "{app_role}"')
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
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"alembic upgrade head failed on {PERF_DATABASE}:\n{result.stderr}")
