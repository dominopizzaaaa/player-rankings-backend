from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()  # Optional if you're also running locally with a .env file

DATABASE_URL = os.getenv("DATABASE_URL")


# ✅ Use create_async_engine for async operations
engine = create_async_engine(DATABASE_URL, echo=True)

# ✅ Create an async session
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
)

# ✅ Define Base for models
Base = declarative_base()

# ✅ Dependency to get the async session
async def get_db():
    async with SessionLocal() as session:
        yield session
        

async_session = SessionLocal
