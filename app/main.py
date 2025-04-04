from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import uvicorn
import logging
from dotenv import load_dotenv

from app.database import Base, engine, get_db
from app.models import Player
from app.auth import router as auth_router
from app.routers.players import router as players_router
from app.routers.matches import router as matches_router
from app.routers import tournaments


# ✅ Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize FastAPI app
app = FastAPI()

# ✅ CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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

# ✅ Run locally
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
