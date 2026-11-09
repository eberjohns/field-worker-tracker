import asyncio
from logging.config import fileConfig

import geoalchemy2  # noqa: F401
from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import fw.modules.attendance.models  # noqa: F401
import fw.modules.audit.models  # noqa: F401
import fw.modules.events.models  # noqa: F401
import fw.modules.identity.models  # noqa: F401
import fw.modules.imports.models  # noqa: F401
import fw.modules.jobs.models  # noqa: F401
import fw.modules.notifications.models  # noqa: F401
import fw.modules.org.models  # noqa: F401
import fw.modules.payroll.models  # noqa: F401
import fw.modules.scheduling.models  # noqa: F401
import fw.modules.settings.models  # noqa: F401
import fw.modules.sync.models  # noqa: F401
from fw.core.config import get_settings
from fw.core.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
# Use DATABASE_MIGRATOR_URL if available, else DATABASE_URL
database_url = settings.DATABASE_MIGRATOR_URL or settings.DATABASE_URL
config.set_main_option("sqlalchemy.url", database_url)

# PostGIS, Tiger Geocoder, and Topology internal tables to ignore during autogenerate / alembic check
EXCLUDED_TABLE_PREFIXES = (
    "tiger",
    "topology",
    "idx_",
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
)
EXCLUDED_TABLES = {
    "spatial_ref_sys",
    "geometry_columns",
    "geography_columns",
    "raster_columns",
    "raster_overviews",
    "topology",
    "layer",
    "addr",
    "addrfeat",
    "bg",
    "county",
    "county_lookup",
    "countysub_lookup",
    "cousub",
    "direction_lookup",
    "edges",
    "faces",
    "featnames",
    "geocode_settings",
    "geocode_settings_default",
    "loader_lookuptables",
    "loader_platform",
    "loader_variables",
    "pagc_gaz",
    "pagc_lex",
    "pagc_rules",
    "place",
    "place_lookup",
    "secondary_unit_lookup",
    "state",
    "state_lookup",
    "street_type_lookup",
    "tabblock",
    "tabblock20",
    "tract",
    "zcta5",
    "zip_lookup",
    "zip_lookup_all",
    "zip_lookup_base",
    "zip_state",
    "zip_state_loc",
}


def include_object(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        if name in EXCLUDED_TABLES or any(
            name.startswith(prefix) for prefix in EXCLUDED_TABLE_PREFIXES
        ):
            return False
    elif type_ == "index":
        if hasattr(obj, "table") and (
            obj.table.name in EXCLUDED_TABLES
            or any(obj.table.name.startswith(prefix) for prefix in EXCLUDED_TABLE_PREFIXES)
        ):
            return False
        if name and any(name.startswith(prefix) for prefix in EXCLUDED_TABLE_PREFIXES):
            return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
