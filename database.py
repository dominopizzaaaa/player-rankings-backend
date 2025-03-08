from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = "postgresql+asyncpg://postgres:ZfzDajaNYKHmRrrmSKEpiPCnSjChMceY@metro.proxy.rlwy.net:54065/railway"

# Create the async database engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a session
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Base class for models
Base = declarative_base()

# Dependency to get a session
async def get_db():
    async with SessionLocal() as session:
        yield session
