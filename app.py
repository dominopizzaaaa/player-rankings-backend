from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String
from pydantic import BaseModel
import os

# 🚀 Load Database URL from Railway
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:ZfzDajaNYKHmRrrmSKEpiPCnSjChMceY@metro.proxy.rlwy.net:54065/railway")

# 🚀 Database Setup
engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

# 🚀 Dependency to get DB session
async def get_db():
    async with SessionLocal() as session:
        yield session

# 🚀 Define Models
class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    rating = Column(Integer, default=1500)
    matches = Column(Integer, default=0)

# 🚀 FastAPI App
app = FastAPI()

@app.get("/")
def home():
    return {"message": "Welcome to the Elo Ranking System!"}

# 🚀 Request Models
class PlayerCreate(BaseModel):
    name: str

class MatchResult(BaseModel):
    player1: str
    player2: str
    winner: str

# 🚀 Initialize Database
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 🚀 Add Player API
@app.post("/add_player")
async def add_player(player: PlayerCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(f"SELECT * FROM players WHERE name = '{player.name}'")
    existing_player = result.fetchone()
    
    if existing_player:
        raise HTTPException(status_code=400, detail="Player already exists.")
    
    new_player = Player(name=player.name)
    db.add(new_player)
    await db.commit()
    
    return {"message": f"Player {player.name} added successfully!", "rating": 1500, "matches": 0}

# 🚀 Elo Calculation Function
def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)

# 🚀 Submit Match API
@app.post("/submit_match")
async def submit_match(result: MatchResult, db: AsyncSession = Depends(get_db)):
    players = await db.execute(f"SELECT * FROM players WHERE name IN ('{result.player1}', '{result.player2}')")
    players = players.fetchall()

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

    await db.execute(f"UPDATE players SET rating={round(new_rating1)}, matches=matches+1 WHERE name='{player1.name}'")
    await db.execute(f"UPDATE players SET rating={round(new_rating2)}, matches=matches+1 WHERE name='{player2.name}'")
    await db.commit()

    return {
        "player1": result.player1,
        "new_rating1": round(new_rating1),
        "games_played_p1": games_played_p1 + 1,
        "player2": result.player2,
        "new_rating2": round(new_rating2),
        "games_played_p2": games_played_p2 + 1,
    }

# 🚀 Get Rankings API
@app.get("/rankings")
async def get_rankings(db: AsyncSession = Depends(get_db)):
    rankings = await db.execute("SELECT name, rating, matches FROM players ORDER BY rating DESC")
    return [{"name": r.name, "rating": r.rating, "matches": r.matches} for r in rankings.fetchall()]
