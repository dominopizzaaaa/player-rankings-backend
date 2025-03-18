import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.database import Base  # ✅ Import your SQLAlchemy models

# Load Alembic Config
config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

# ✅ Use a **SYNC** engine for Alembic migrations
connectable = create_engine(
    config.get_main_option("sqlalchemy.url"),  # Uses the sync DB URL from alembic.ini
    poolclass=pool.NullPool,
)

def run_migrations_online():
    """Run migrations using a synchronous database engine."""
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()  # ✅ Call this directly, no async needed
