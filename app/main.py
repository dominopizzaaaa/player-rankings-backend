from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, schemas, database
from .models import Match, Player
from .schemas import MatchCreate, MatchResponse
from .database import engine, SessionLocal
from .elo import calculate_elo
import uvicorn

# Initialize the database
models.Base.metadata.create_all(bind=engine)

# Create the FastAPI app
app = FastAPI()

# CORS configuration to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow requests from frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Player Rankings API is running!"}

# Create a player
@app.post("/players", response_model=schemas.PlayerResponse)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(**player.dict())
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

# Get all players
@app.get("/players", response_model=list[schemas.PlayerResponse])
def get_players(db: Session = Depends(get_db)):
    return db.query(models.Player).all()

# Get a player by ID
@app.get("/players/{player_id}", response_model=schemas.PlayerResponse)
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player

# Update a player's rating
@app.put("/players/{player_id}/rating", response_model=schemas.PlayerResponse)
def update_rating(player_id: int, rating: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    player.rating = rating
    db.commit()
    db.refresh(player)
    return player

# Create a player
@app.post("/players", response_model=schemas.PlayerResponse)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    db_player = models.Player(
        name=player.name,
        handedness=player.handedness,
        forehand_rubber=player.forehand_rubber,
        backhand_rubber=player.backhand_rubber,
        blade=player.blade,
        age=player.age,
        gender=player.gender
    )
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

# Delete a player
@app.delete("/players/{player_id}")
def delete_player(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    db.delete(player)
    db.commit()
    return {"message": "Player deleted successfully"}

# Submit match results and update Elo ratings
@app.post("/matches", response_model=schemas.MatchResponse)
def submit_match(match: MatchCreate, db: Session = Depends(get_db)):
    player1 = db.query(Player).filter(Player.id == match.player1_id).first()
    player2 = db.query(Player).filter(Player.id == match.player2_id).first()

    if not player1 or not player2:
        raise HTTPException(status_code=404, detail="One or both players not found")

    # Ensure winner ID is correct
    if match.winner not in [match.player1_id, match.player2_id]:
        raise HTTPException(status_code=400, detail="Winner must be one of the two players")

    # Determine winner & loser
    if match.winner == match.player1_id:
        winner, loser = player1, player2
    else:
        winner, loser = player2, player1

    # Calculate new Elo ratings
    new_winner_elo, new_loser_elo = calculate_elo(winner.rating, loser.rating)

    # Update player ratings
    winner.rating = new_winner_elo
    loser.rating = new_loser_elo
    winner.matches_played += 1
    loser.matches_played += 1

    # Save match result
    db_match = Match(
        player1_id=match.player1_id,
        player2_id=match.player2_id,
        player1_score=match.player1_score,
        player2_score=match.player2_score,
        winner=match.winner  # ✅ Store winner
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)

    return db_match

# Get all match history
@app.get("/matches", response_model=list[schemas.MatchResponse])
def get_matches(db: Session = Depends(get_db)):
    return db.query(models.Match).all()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
