from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone

from app.models import Tournament, GroupingMode
from app.schemas import TournamentCreate, TournamentResponse
from app.database import get_db
from app.auth import is_admin

router = APIRouter(prefix="/tournaments", tags=["Tournaments"])

# ✅ Create a new tournament (admin only)
@router.post("/", response_model=TournamentResponse)
async def create_tournament(tournament: TournamentCreate, db: AsyncSession = Depends(get_db), admin=True): #Depends(is_admin)
    new_tournament = Tournament(
        name=tournament.name,
        date=tournament.date,
        num_players=tournament.num_players,
        num_groups=tournament.num_groups,
        knockout_size=tournament.knockout_size,
        grouping_mode=tournament.grouping_mode,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_tournament)
    await db.commit()
    await db.refresh(new_tournament)
    return new_tournament

# ✅ Get all tournaments (public)
@router.get("/", response_model=list[TournamentResponse])
async def get_all_tournaments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).order_by(Tournament.date.desc()))
    tournaments = result.scalars().all()
    return tournaments

# ✅ Get a specific tournament by ID (public)
@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(tournament_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tournament).where(Tournament.id == tournament_id))
    tournament = result.scalars().first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")
    return tournament
