"""Reset the database to a clean bootstrap state (same as Settings > Reset database, Admin).

Clears every master and transactional table, then re-creates ADMIN001 (a standalone Admin user,
password ChangeMe123!), the default company settings and the managed lists. The master data can
then be imported again (Imports page, or the demo workbook in tools/demo_data/).

    uv run --directory backend python ../tools/reset_database.py

Refused when APP_ENV is production. It uses the database the app is configured for
(DATABASE_URL), which it prints first.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy.engine import make_url  # noqa: E402

from fw.api.settings import reset_to_bootstrap_state  # noqa: E402
from fw.core.config import get_settings  # noqa: E402
from fw.core.db import async_session_factory, engine  # noqa: E402


async def reset_db() -> None:
    settings = get_settings()
    if (settings.APP_ENV or "").lower() == "production":
        sys.exit("Refused: APP_ENV is production")
    url = make_url(settings.DATABASE_URL)
    print(f"Resetting {url.host}:{url.port or 5432}/{url.database} ...")
    async with async_session_factory() as session:
        await reset_to_bootstrap_state(session)
        await session.commit()
    await engine.dispose()
    print("Done: only ADMIN001 (password ChangeMe123!) and the default settings remain.")


if __name__ == "__main__":
    asyncio.run(reset_db())
