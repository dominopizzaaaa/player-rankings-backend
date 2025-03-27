from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import List
from datetime import date as dt_date


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
    date: dt_date
    num_groups: int
    knockout_size: int
    grouping_mode: GroupingMode
    player_ids: List[int]  # ✅ New field

class TournamentResponse(BaseModel):
    id: int
    name: str
    date: dt_date
    num_players: int
    num_groups: int
    knockout_size: int
    grouping_mode: GroupingMode
    created_at: dt_date
    player_ids: List[int]  # ✅ Required in response

    class Config:
        orm_mode = True
