from typing import Optional
from pydantic import BaseModel
from datetime import date, datetime
from enum import Enum

class PlayerCreate(BaseModel):
    name: str
    matches: int = 0
    rating: int = 1500
    handedness: Optional[str] = None
    forehand_rubber: Optional[str] = None
    backhand_rubber: Optional[str] = None
    blade: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None

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

class GroupingMode(str, Enum):
    ranked = "ranked"
    random = "random"

class TournamentCreate(BaseModel):
    name: str
    date: date
    num_players: int
    num_groups: int
    knockout_size: int
    grouping_mode: GroupingMode

class TournamentResponse(TournamentCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True