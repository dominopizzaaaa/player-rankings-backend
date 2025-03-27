from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import logging

from app.models import Player, Match
from app.schemas import MatchResult
from app.database import get_db
from app.auth import is_admin

app = APIRouter()
logger = logging.getLogger(__name__)

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


