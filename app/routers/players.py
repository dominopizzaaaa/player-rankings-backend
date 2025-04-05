from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete
import logging

from app.models import Player, Match, TournamentPlayer
from app.schemas import PlayerCreate
from app.database import get_db
from app.auth import is_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/")
async def add_player(player: PlayerCreate, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    new_player = Player(
        name=player.name,
        matches=player.matches,
        rating=player.rating,
        handedness=player.handedness,
        forehand_rubber=player.forehand_rubber,
        backhand_rubber=player.backhand_rubber,
        blade=player.blade,
        age=player.age,
        gender=player.gender
    )
    db.add(new_player)
    await db.commit()
    
    return {"message": f"Player {player.name} added successfully!", "rating": 1500, "matches": 0}

@router.get("/")
async def get_players(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Player))
    players = result.scalars().all()
    return [{"id": p.id, "name": p.name, "rating": p.rating, "matches": p.matches} for p in players]

@router.get("/{player_id}")
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
    
@router.delete("/{player_id}")
async def delete_player(player_id: int, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalars().first()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found.")

    # ✅ Optional: Pre-check if player is in a tournament
    tournament_check = await db.execute(select(TournamentPlayer).where(TournamentPlayer.player_id == player_id))
    if tournament_check.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Cannot delete player because they are part of a tournament."
        )

    # ✅ Delete all matches where the player was involved
    await db.execute(delete(Match).where((Match.player1_id == player_id) | (Match.player2_id == player_id)))

    # ✅ Delete the player after removing matches
    await db.delete(player)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete player due to existing tournament or match links."
        )

    return {"message": f"Player {player.name} and their matches deleted successfully."}

@router.patch("/{player_id}")
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

