from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.database import Base

import asyncio

# Load Alembic configuration
config = context.config

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Use asyncmy instead of pymysql
target_metadata = Base.metadata


# ✅ Run migrations with async engine
def run_migrations_online():
    """
    Run migrations in 'online' mode using an asynchronous database engine.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async def do_run_migrations():
        async with connectable.begin() as connection:
            await connection.run_sync(context.configure, connection=connection, target_metadata=target_metadata)
            await connection.run_sync(context.run_migrations)

    asyncio.run(do_run_migrations())


if context.is_offline_mode():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
