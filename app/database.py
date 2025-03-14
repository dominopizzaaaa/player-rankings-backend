from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ✅ Use asyncmy instead of pymysql
DATABASE_URL="mysql+asyncmy://root:dominopizza@35.240.170.40:3306/player_rankings"

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
