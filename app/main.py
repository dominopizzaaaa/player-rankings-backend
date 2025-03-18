from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, delete
from sqlalchemy.orm import relationship, joinedload
from pydantic import BaseModel
import uvicorn
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
import logging

# ✅ Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Import async database configurations
from app.database import Base, engine, get_db, SessionLocal

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    rating = Column(Integer, default=1500)
    matches = Column(Integer, default=0)

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player1_score = Column(Integer, nullable=False, default=0)
    player2_score = Column(Integer, nullable=False, default=0)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    match_winner = relationship("Player", foreign_keys=[winner_id])

class PlayerCreate(BaseModel):
    name: str

class MatchResult(BaseModel):
    player1_id: int
    player2_id: int
    player1_score: int
    player2_score: int
    winner_id: int

class MatchResponse(BaseModel):
    player1: str
    new_rating1: int
    games_played_p1: int
    player2: str
    new_rating2: int
    games_played_p2: int

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://player-rankings-frontend-omega.vercel.app",  # ✅ Allow frontend domain
        "http://localhost:3000",  # ✅ Allow local dev frontend
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # ✅ Ensure all methods are allowed
    allow_headers=["*"],  # ✅ Allow all headers
    expose_headers=["*"],  # ✅ Expose headers in response
)

@app.get("/")
async def home():
    return {"message": "Player Rankings API is running!"}

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

@app.get("/players")
async def get_players(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player))
    players = result.scalars().all()
    return [{"id": p.id, "name": p.name, "rating": p.rating, "matches": p.matches} for p in players]

@app.get("/players/{player_id}")
async def get_player(player_id: int, db: AsyncSession = Depends(get_db)):
    logger.info(f"Fetching player with ID: {player_id}")

    try:
        result = await db.execute(select(Player).where(Player.id == player_id))
        player = result.scalars().first()

        if not player:
            logger.warning(f"Player {player_id} not found.")
            raise HTTPException(status_code=404, detail="Player not found.")

        logger.info(f"Player found: {player.name} (ID: {player.id})")

        return {
            "id": player.id,
            "name": player.name,
            "rating": player.rating,
            "matches": player.matches,
            "handedness": player.handedness or "Unknown",
            "forehand_rubber": player.forehand_rubber or "Unknown",
            "backhand_rubber": player.backhand_rubber or "Unknown",
            "blade": player.blade or "Unknown",
            "age": player.age if player.age is not None else "Unknown",
            "gender": player.gender or "Unknown"
        }


    except Exception as e:
        logger.error(f"Error fetching player {player_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)

@app.post("/matches")
async def submit_match(result: MatchResult, db: AsyncSession = Depends(get_db)):
    logger.info("Received match submission: %s", result.dict())

    # ✅ Fetch players by ID instead of names
    stmt = select(Player).where(Player.id.in_([result.player1_id, result.player2_id]))
    players = (await db.execute(stmt)).scalars().all()

    logger.info("Fetched players: %s", [(p.id, p.name, p.rating, p.matches) for p in players])

    if len(players) < 2:
        logger.error("Both players must exist in the database.")
        raise HTTPException(status_code=400, detail="Both players must exist.")

    player1, player2 = players if players[0].id == result.player1_id else players[::-1]

    if result.winner_id not in [player1.id, player2.id]:
        logger.error("Winner ID %s is not one of the players.", result.winner_id)
        raise HTTPException(status_code=400, detail="Winner must be one of the players.")

    # ✅ Determine winner
    winner = player1 if result.winner_id == player1.id else player2
    logger.info("Winner determined: %s", winner.name)

    # ✅ Save match to DB
    new_match = Match(
        player1_id=player1.id, 
        player2_id=player2.id, 
        player1_score=result.player1_score, 
        player2_score=result.player2_score, 
        winner_id=winner.id,
        timestamp=datetime.now(timezone.utc)  # ✅ Explicitly set timestamp
    )
    db.add(new_match)
    logger.info("Match added to DB session: %s", new_match)

    # ✅ Update player ratings
    games_played_p1 = player1.matches
    games_played_p2 = player2.matches

    if result.winner_id == player1.id:
        new_rating1 = calculate_elo(player1.rating, player2.rating, 1, games_played_p1)
        new_rating2 = calculate_elo(player2.rating, player1.rating, 0, games_played_p2)
    else:
        new_rating1 = calculate_elo(player1.rating, player2.rating, 0, games_played_p1)
        new_rating2 = calculate_elo(player2.rating, player1.rating, 1, games_played_p2)

    logger.info("New ratings calculated: %s -> %s, %s -> %s", 
                player1.name, round(new_rating1), 
                player2.name, round(new_rating2))

    player1.rating = round(new_rating1)
    player1.matches += 1
    player2.rating = round(new_rating2)
    player2.matches += 1

    await db.commit()
    logger.info("Match committed to DB.")

    return MatchResponse(
            player1=player1.name,
            new_rating1=round(new_rating1),
            games_played_p1=games_played_p1 + 1,
            player2=player2.name,
            new_rating2=round(new_rating2),
            games_played_p2=games_played_p2 + 1
        )

@app.get("/matches")
async def get_matches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(joinedload(Match.player1), joinedload(Match.player2), joinedload(Match.match_winner))
    )
    matches = result.scalars().all()

    return [
        {
            "id": m.id,
            "player1": m.player1.name,
            "player1_id": m.player1.id,
            "player2": m.player2.name,
            "player2_id": m.player2.id,
            "player1_score": m.player1_score,
            "player2_score": m.player2_score,
            "winner_id": m.winner_id,
            "timestamp": m.timestamp
        }
        for m in matches
    ]

@app.get("/rankings")
async def get_rankings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).order_by(Player.rating.desc()))
    rankings = result.scalars().all()

    return [{"name": r.name, "rating": r.rating, "matches": r.matches} for r in rankings]

@app.delete("/players/{player_id}")
async def delete_player(player_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalars().first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    # ✅ Delete all matches where the player was involved
    await db.execute(delete(Match).where((Match.player1_id == player_id) | (Match.player2_id == player_id)))

    # ✅ Delete the player after removing matches
    await db.delete(player)
    await db.commit()

    return {"message": f"Player {player.name} and their matches deleted successfully."}

@app.delete("/matches/{match_id}")
async def delete_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalars().first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")

    await db.delete(match)
    await db.commit()

    return {"message": f"Match {match.id} deleted successfully."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
