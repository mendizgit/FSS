"""Alembic environment (async). The DB URL comes from Settings (env), never from alembic.ini."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import tss.db.models  # noqa: F401  (registers all tables on Base.metadata)
from tss.core.errors import StorageError
from tss.core.settings import load_config_or_exit
from tss.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return load_config_or_exit().settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        _database_url(), connect_args={"server_settings": {"timezone": "UTC"}}
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run_migrations)
    except OSError as exc:
        raise StorageError(
            "alembic", "migrate", "connect", f"database unreachable ({type(exc).__name__})"
        ) from exc
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
