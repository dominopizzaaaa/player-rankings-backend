from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, delete
from sqlalchemy.orm import relationship, joinedload
from pydantic import BaseModel
import uvicorn
from datetime import datetime, timezone, timedelta
import logging
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
import os

# ✅ Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
load_dotenv()

# ✅ Get admin credentials from .env
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ✅ Import async database configurations
from app.database import Base, engine, get_db, SessionLocal

# ✅ Function to check if the user is an admin
async def is_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: Admins only",
                headers={"WWW-Authenticate": "Bearer"}
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login to change details",
            headers={"WWW-Authenticate": "Bearer realm='Login required'"}
        )

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # ✅ Explicit length added
    matches = Column(Integer, default=0)
    rating = Column(Integer, default=1500)
    handedness = Column(String(10), nullable=True)  # ✅ Explicit length added
    forehand_rubber = Column(String(100), nullable=True)  # ✅ Explicit length added
    backhand_rubber = Column(String(100), nullable=True)  # ✅ Explicit length added
    blade = Column(String(100), nullable=True)  # ✅ Explicit length added
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # ✅ Explicit length added

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
    allow_origins = [
        "https://player-rankings-frontend-omega.vercel.app",
        "https://player-rankings-frontend-xiao-bai-qius-projects.vercel.app",
        "https://player-rankings-frontend-git-main-xiao-bai-qius-projects.vercel.app",
        "https://player-rankings-frontend-9a11owqx4-xiao-bai-qius-projects.vercel.app",
        "https://player-rankings-frontend-auaueau4n-xiao-bai-qius-projects.vercel.app",  # ✅ Add this
        "http://localhost:3000",  # ✅ Allow local dev frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],  # ✅ Ensure all methods are allowed
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
async def add_player(player: PlayerCreate, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    new_player = Player(name=player.name)  # ✅ No duplicate check
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
    print(f"Fetching player with ID: {player_id}")

    try:
        result = await db.execute(select(Player).where(Player.id == player_id))
        player = result.scalars().first()

        if not player:
            logger.warning(f"Player {player_id} not found.")
            raise HTTPException(status_code=404, detail="Player not found.")

        # Debugging: Check if 'handedness' exists
        if not hasattr(player, "handedness"):
            print("DEBUG: 'handedness' attribute is missing from the Player model!")
            raise HTTPException(status_code=500, detail="Player model does not match database schema")

        logger.info(f"Player found: {player.name} (ID: {player.id})")

        return {
            "id": player.id,
            "name": player.name,
            "rating": player.rating,
            "matches": player.matches if player.matches is not None else 0,
            "handedness": player.handedness if player.handedness is not None else "Unknown",
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

    # ✅ Fetch players using async execution
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

    # ✅ Ensure the session commits properly
    try:
        await db.commit()
        logger.info("Match committed to DB.")
    except Exception as e:
        await db.rollback()
        logger.error("Error committing match: %s", e)
        raise HTTPException(status_code=500, detail="Database commit error")

    return {
        "message": "Match successfully recorded",
        "player1": player1.name,
        "player1_new_rating": player1.rating,
        "player2": player2.name,
        "player2_new_rating": player2.rating
    }

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
async def delete_player(player_id: int, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
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
async def delete_match(match_id: int, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    # ✅ Check if the match exists
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalars().first()

    if not match:
        logger.warning(f"Delete failed: Match {match_id} not found.")
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found.")

    # ✅ Delete the match
    await db.delete(match)
    await db.commit()
    
    logger.info(f"Match {match_id} deleted successfully.")
    return {"message": f"Match {match_id} deleted successfully."}


@app.patch("/players/{player_id}")
async def update_player(player_id: int, player_update: dict, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    stmt = select(Player).where(Player.id == player_id)
    result = await db.execute(stmt)
    player = result.scalars().first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    for key, value in player_update.items():
        if hasattr(player, key) and value is not None:
            setattr(player, key, value)

    await db.commit()
    await db.refresh(player)
    return player

@app.patch("/matches/{match_id}")
async def update_match(match_id: int, update_data: dict, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    # ✅ Fetch the match asynchronously
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalars().first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")

    # ✅ Update match attributes dynamically
    for key, value in update_data.items():
        if hasattr(match, key) and value is not None:
            setattr(match, key, value)

    await db.commit()
    return {"message": f"Match {match_id} updated successfully.", "updated_data": update_data}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)


# LOGGING IN & SECURITY
    
# ✅ Get secrets from environment variables
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_key")  # Fallback in case it's missing
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ✅ Load Admin Credentials Securely
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password123")

# Optional: Fake Admin DB Example (Could be removed if using a real database)
fake_admin_db = {
    ADMIN_USERNAME: {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD, "role": "admin"}
}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    print("DEBUG: Login attempt with", form_data.username, form_data.password)  # Debugging

    user = fake_admin_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token_data = {"sub": user["username"], "role": user["role"]}
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token, "token_type": "bearer"}

# Helper function to create a JWT token
def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ Login route to authenticate admin and return token
@app.post("/login")
async def login(request: Request):
    credentials = await request.json()
    if credentials["username"] != ADMIN_USERNAME or credentials["password"] != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": credentials["username"]}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": token, "token_type": "bearer"}

# ✅ Middleware to protect admin routes
def verify_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username != ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="Admin access required")
        return username
    except JWTError:
        raise HTTPException(status_code=403, detail="Invalid token")

# ✅ Protect restricted routes
@app.get("/admin-only")
async def admin_dashboard(username: str = Depends(verify_admin)):
    return {"message": "Welcome, Admin!"}

