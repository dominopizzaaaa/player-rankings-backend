from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
from app.models import Tournament, GroupingMode, TournamentPlayer, TournamentMatch, Player
from app.schemas import TournamentCreate, TournamentResponse, TournamentDetailsResponse, TournamentMatchResponse
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.auth import is_admin
import random
from sqlalchemy.orm import selectinload, aliased
from typing import List

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])

# ✅ Create a new tournament (admin only)
@router.post("/", response_model=dict)
async def create_tournament(tournament: TournamentCreate, db: AsyncSession = Depends(get_db), admin=True):
    new_tournament = Tournament(
        name=tournament.name,
        date=tournament.date,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=datetime.now(timezone.utc),
        num_players=len(tournament.player_ids)
    )

    db.add(new_tournament)
    await db.flush()  # Get tournament ID

    players = tournament.player_ids[:]

    if tournament.grouping_mode == GroupingMode.RANDOM:
        random.shuffle(players)

    if tournament.num_groups > 0:
        for i, pid in enumerate(players):
            group_number = i % tournament.num_groups
            db.add(TournamentPlayer(
                tournament_id=new_tournament.id,
                player_id=pid,
                group_number=group_number
            ))
    else:
        for pid in players:
            db.add(TournamentPlayer(
                tournament_id=new_tournament.id,
                player_id=pid,
                group_number=None
            ))
    tournament_id = new_tournament.id
    await db.commit()
    return {"message": "Tournament created successfully", "tournament_id": tournament_id}

# ✅ Get all tournaments (public)
from sqlalchemy.orm import selectinload
@router.get("/", response_model=List[TournamentResponse])
async def get_all_tournaments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tournament)
        .options(selectinload(Tournament.players))  # ✅ Eager load
        .order_by(Tournament.date.desc())
    )
    tournaments = result.scalars().all()

    # Manually map player_ids for the response
    response = []
    for t in tournaments:
        player_ids = [tp.player_id for tp in t.players]  # ✅ Now safe to access
        response.append(TournamentResponse(
            id=t.id,
            name=t.name,
            date=t.date,
            num_players=t.num_players,
            num_groups=t.num_groups,
            knockout_size=t.knockout_size,
            grouping_mode=t.grouping_mode,
            created_at=t.created_at,
            player_ids=player_ids
        ))

    return response



# ✅ Get a specific tournament by ID (public)
@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(tournament_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")
    
    player_ids = [tp.player_id for tp in tournament.players]
    return TournamentResponse(
        id=tournament.id,
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=tournament.created_at,
        player_ids=player_ids
    )

@router.get("/{tournament_id}/details", response_model=TournamentDetailsResponse)
async def get_tournament_details(tournament_id: int, db: AsyncSession = Depends(get_db)):
    # 1. Get the tournament
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")

    # 2. Get all matches for this tournament
    Player1 = aliased(Player)
    Player2 = aliased(Player)

    match_query = (
        select(
            TournamentMatch.id,
            TournamentMatch.tournament_id,
            TournamentMatch.player1_id,
            TournamentMatch.player2_id,
            Player1.name.label("player1_name"),
            Player2.name.label("player2_name"),
            TournamentMatch.player1_score,
            TournamentMatch.player2_score,
            TournamentMatch.winner_id,
            TournamentMatch.round,
            TournamentMatch.stage,
        )
        .join(Player1, TournamentMatch.player1_id == Player1.id)
        .join(Player2, TournamentMatch.player2_id == Player2.id)
        .where(TournamentMatch.tournament_id == tournament_id)
    )
    result = await db.execute(match_query)
    matches = result.all()

    # 3. Categorize matches
    group_matches = []
    knockout_matches = []
    individual_matches = []

    for match in matches:
        match_obj = TournamentMatchResponse(
            id=match.id,
            player1_id=match.player1_id,
            player2_id=match.player2_id,
            player1_name=match.player1_name,
            player2_name=match.player2_name,
            player1_score=match.player1_score,
            player2_score=match.player2_score,
            winner_id=match.winner_id,
            round=match.round,
            stage=match.stage,
        )
        
        if match.stage == "group":
            group_matches.append(match_obj)
        elif match.stage == "knockout":
            knockout_matches.append(match_obj)
        else:
            individual_matches.append(match_obj)


    # 4. Final standings (placeholder for now, implement logic later)
    final_standings = []  # You can add logic to determine 1st–4th based on knockout

    # 5. Return detailed response
    return TournamentDetailsResponse(
        id=tournament.id,
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=tournament.created_at,
        group_matches=group_matches,
        knockout_matches=knockout_matches,
        individual_matches=individual_matches,
        final_standings=final_standings,
    )
