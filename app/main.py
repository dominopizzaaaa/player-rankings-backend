from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uvicorn
import logging
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize FastAPI app with redirect_slashes=False to avoid automatic redirects
app = FastAPI(redirect_slashes=False)

# ✅ Allow all hosts (or specify your own domain)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# ✅ Import internal modules
from app.database import Base, engine, get_db
from app.models import Player
from app.auth import router as auth_router
from app.routers.players import router as players_router
from app.routers.matches import router as matches_router
from app.routers import tournaments

# ✅ Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ Health check
@app.get("/")
async def home():
    return {"message": "Player Rankings API is running!"}

# ✅ Create DB tables on startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ✅ Rankings endpoint
@app.get("/rankings")
async def get_rankings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.rating.desc()))
    rankings = result.scalars().all()
    return [{"name": r.name, "rating": r.rating, "matches": r.matches} for r in rankings]

# ✅ Register routers
app.include_router(players_router, prefix="/players", tags=["Players"])
app.include_router(matches_router, prefix="/matches", tags=["Matches"])
app.include_router(auth_router, tags=["Auth"])
app.include_router(tournaments.router, prefix="/tournaments", tags=["Tournaments"])

# ✅ Uvicorn entry point with proxy headers enabled
if __name__ == "__main__":
    import os

    # Optional: Allow from specific IP or set via environment variable
    forwarded_ips = os.getenv("FORWARDED_ALLOW_IPS", "*")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        proxy_headers=True,           # ✅ Trust proxy headers
        forwarded_allow_ips=forwarded_ips,  # ✅ Accept X-Forwarded-* headers
    )

