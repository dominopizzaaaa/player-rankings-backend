from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.inspection import inspect
from datetime import datetime
import logging
from pytz import timezone as dt_timezone
from app.models import Player, Match, SetScore
from app.schemas import MatchResult, HeadToHeadResponse
from app.database import get_db
from app.auth import is_admin

router = APIRouter()
logger = logging.getLogger(__name__)
sgt = dt_timezone("Asia/Singapore")

def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)

@router.post("/")
async def submit_match(result: MatchResult, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    logger.info("Received match submission: %s", result.dict())

    stmt = select(Player).where(Player.id.in_([result.player1_id, result.player2_id]))
    players = (await db.execute(stmt)).scalars().all()

    if len(players) < 2:
        raise HTTPException(status_code=400, detail="Both players must exist.")

    player1, player2 = players if players[0].id == result.player1_id else players[::-1]

    if result.winner_id not in [player1.id, player2.id]:
        raise HTTPException(status_code=400, detail="Winner must be one of the players.")

    # ✅ Determine outcome
    outcome1 = 1 if result.winner_id == player1.id else 0
    outcome2 = 1 - outcome1

    # ✅ Calculate new ratings
    new_rating1 = int(calculate_elo(player1.rating, player2.rating, outcome1, player1.matches or 0))
    new_rating2 = int(calculate_elo(player2.rating, player1.rating, outcome2, player2.matches or 0))

    # ✅ Update player stats
    player1.rating = new_rating1
    player2.rating = new_rating2
    player1.matches = (player1.matches or 0) + 1
    player2.matches = (player2.matches or 0) + 1

    # ✅ Create match record (with new fields)
    timestamp = result.timestamp or datetime.now(sgt)
    # Calculate total sets won
    p1_total = sum(1 for s in result.sets if s.player1_score > s.player2_score)
    p2_total = sum(1 for s in result.sets if s.player2_score > s.player1_score)

    new_match = Match(
        player1_id=player1.id,
        player2_id=player2.id,
        player1_score=p1_total,
        player2_score=p2_total,
        winner_id=result.winner_id,
        timestamp=timestamp,
    )

    db.add(new_match)

    # ✅ Add set scores
    await db.flush()  # Ensure match.id is available
    for s in result.sets:
        db.add(SetScore(
            match_id=new_match.id,
            set_number=s.set_number,
            player1_score=s.player1_score,
            player2_score=s.player2_score,
        ))

    try:
        await db.commit()
        await db.refresh(player1)
        await db.refresh(player2)
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

@router.get("/")
async def get_matches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(
            joinedload(Match.player1),
            joinedload(Match.player2),
            joinedload(Match.match_winner),
            joinedload(Match.set_scores),
        )
    )
    matches = result.unique().scalars().all()

    # Filter out bye matches (i.e. player1 or player2 is None)
    valid_matches = [m for m in matches if m.player1 and m.player2]

    # Sort by timestamp (earliest first)
    valid_matches.sort(key=lambda m: m.timestamp or 0)

    return [
        {
            "id": m.id,
            "player1_id": m.player1.id,
            "player1": m.player1.name,
            "player2_id": m.player2.id,
            "player2": m.player2.name,
            "player1_score": m.player1_score,
            "player2_score": m.player2_score,
            "winner_id": m.winner_id,
            "round": m.round,
            "stage": m.stage,
            "timestamp": m.timestamp.astimezone(sgt).strftime("%-d %b %Y, %H:%M") if m.timestamp else None,
            "set_scores": [
                {
                    "set_number": s.set_number,
                    "player1_score": s.player1_score,
                    "player2_score": s.player2_score
                }
                for s in m.set_scores
            ]
        }
        for m in valid_matches
    ]

@router.delete("/{match_id}")
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

@router.patch("/{match_id}")
async def update_match(match_id: int, update_data: dict, db: AsyncSession = Depends(get_db), admin=Depends(is_admin)):
    result = await db.execute(select(Match).where(Match.id == match_id))
    match = result.scalars().first()

    if not match:
        raise HTTPException(status_code=404, detail="Match not found.")

    # ✅ Update match columns
    column_keys = {column.key for column in inspect(Match).mapper.column_attrs}
    for key, value in update_data.items():
        if key in column_keys and value is not None:
            setattr(match, key, value)

    # ✅ If sets are provided, update them
    if "sets" in update_data and isinstance(update_data["sets"], list):
        # Delete old sets
        await db.execute(delete(SetScore).where(SetScore.match_id == match.id))

        # Add new sets
        for s in update_data["sets"]:
            db.add(SetScore(
                match_id=match.id,
                set_number=s["set_number"],
                player1_score=s["player1_score"],
                player2_score=s["player2_score"],
            ))

    await db.commit()
    await db.refresh(match)

    return {
        "message": f"Match {match_id} updated successfully.",
        "updated_data": update_data,
    }

@router.get("/head-to-head", response_model=HeadToHeadResponse)
async def head_to_head(player1_id: int, player2_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(joinedload(Match.set_scores), joinedload(Match.tournament))  # ✅ add this
        .where(
            or_(
                and_(Match.player1_id == player1_id, Match.player2_id == player2_id),
                and_(Match.player1_id == player2_id, Match.player2_id == player1_id),
            )
        )
    )
    matches = result.unique().scalars().all()

    if not matches:
        raise HTTPException(status_code=404, detail="No matches found between these players.")

    valid_matches = [m for m in matches if m.winner_id and m.timestamp and m.player1_id and m.player2_id]

    if not valid_matches:
        raise HTTPException(status_code=404, detail="No valid matches with results.")

    valid_matches.sort(key=lambda m: m.timestamp, reverse=True)

    stats = {
        "player1_id": player1_id,
        "player2_id": player2_id,
        "matches_played": 0,
        "player1_wins": 0,
        "player2_wins": 0,
        "player1_sets": 0,
        "player2_sets": 0,
        "player1_points": 0,
        "player2_points": 0,
        "match_history": [],
        "most_recent_winner": None,
    }

    for match in valid_matches:
        stats["matches_played"] += 1

        sets = [
            {"player1_score": s.player1_score, "player2_score": s.player2_score}
            for s in match.set_scores
        ]

        p1_set_wins = sum(1 for s in sets if s["player1_score"] > s["player2_score"])
        p2_set_wins = sum(1 for s in sets if s["player2_score"] > s["player1_score"])
        p1_points = sum(s["player1_score"] for s in sets)
        p2_points = sum(s["player2_score"] for s in sets)

        if match.player1_id == player1_id:
            stats["player1_sets"] += p1_set_wins
            stats["player2_sets"] += p2_set_wins
            stats["player1_points"] += p1_points
            stats["player2_points"] += p2_points
        else:
            stats["player1_sets"] += p2_set_wins
            stats["player2_sets"] += p1_set_wins
            stats["player1_points"] += p2_points
            stats["player2_points"] += p1_points

        if match.winner_id == player1_id:
            stats["player1_wins"] += 1
        elif match.winner_id == player2_id:
            stats["player2_wins"] += 1

        stats["match_history"].append({
            "date": match.timestamp,
            "tournament": bool(match.tournament_id),
            "tournament_name": match.tournament.name if match.tournament else None,  # ✅ FIX
            "winner_id": match.winner_id,
            "player1_id": match.player1_id,
            "player2_id": match.player2_id,
            "player1_score": p1_set_wins,
            "player2_score": p2_set_wins,
            "set_scores": sets
        })

    total = stats["matches_played"]
    stats["player1_win_percentage"] = round((stats["player1_wins"] / total) * 100, 2)
    stats["player2_win_percentage"] = round((stats["player2_wins"] / total) * 100, 2)
    stats["most_recent_winner"] = stats["match_history"][0]["winner_id"]

    return stats
