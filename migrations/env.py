import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from vas2font.api import models
from vas2font.api.config import get_settings

target_metadata = models.Base.metadata


def run_migrations_online() -> None:
    async def migrate() -> None:
        engine = create_async_engine(get_settings().database_url)
        async with engine.begin() as connection:
            await connection.run_sync(do_run_migrations)
        await engine.dispose()

    asyncio.run(migrate())


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
