from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel
import uvicorn

# ✅ Import async database configurations
from database import Base, engine, get_db, SessionLocal

# ✅ Define Player Model
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    rating = Column(Integer, default=1500)
    matches = Column(Integer, default=0)

# ✅ FastAPI App
app = FastAPI()

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def home():
    return {"message": "Player Rankings API is running!"}

# ✅ Pydantic Models
class PlayerCreate(BaseModel):
    name: str

class MatchResult(BaseModel):
    player1: str
    player2: str
    winner: str

# ✅ Initialize Database on Startup
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ✅ Add Player API
@app.post("/players")
async def add_player(player: PlayerCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.name == player.name))
    existing_player = result.scalars().first()
    
    if existing_player:
        raise HTTPException(status_code=400, detail="Player already exists.")
    
    new_player = Player(name=player.name)
    db.add(new_player)
    await db.commit()
    
    return {"message": f"Player {player.name} added successfully!", "rating": 1500, "matches": 0}

# ✅ Elo Rating Calculation
def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)

# ✅ Submit Match API
@app.post("/matches")
async def submit_match(result: MatchResult, db: AsyncSession = Depends(get_db)):
    stmt = select(Player).where(Player.name.in_([result.player1, result.player2]))
    players = (await db.execute(stmt)).scalars().all()

    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Both players must exist.")

    player1, player2 = players if players[0].name == result.player1 else players[::-1]

    if result.winner not in [result.player1, result.player2]:
        raise HTTPException(status_code=400, detail="Winner must be one of the players.")

    games_played_p1 = player1.matches
    games_played_p2 = player2.matches

    if result.winner == result.player1:
        new_rating1 = calculate_elo(player1.rating, player2.rating, 1, games_played_p1)
        new_rating2 = calculate_elo(player2.rating, player1.rating, 0, games_played_p2)
    else:
        new_rating1 = calculate_elo(player1.rating, player2.rating, 0, games_played_p1)
        new_rating2 = calculate_elo(player2.rating, player1.rating, 1, games_played_p2)

    player1.rating = round(new_rating1)
    player1.matches += 1
    player2.rating = round(new_rating2)
    player2.matches += 1

    await db.commit()

    return {
        "player1": result.player1,
        "new_rating1": round(new_rating1),
        "games_played_p1": games_played_p1 + 1,
        "player2": result.player2,
        "new_rating2": round(new_rating2),
        "games_played_p2": games_played_p2 + 1,
    }

# ✅ Get Rankings API
@app.get("/rankings")
async def get_rankings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.rating.desc()))
    rankings = result.scalars().all()

    return [{"name": r.name, "rating": r.rating, "matches": r.matches} for r in rankings]

# ✅ Run FastAPI Server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
