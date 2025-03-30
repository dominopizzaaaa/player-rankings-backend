from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any
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
    players_per_group_advancing: int
    player_ids: List[int]  # ✅ New field

class TournamentResponse(BaseModel):
    id: int
    name: str
    date: dt_date
    num_players: int
    num_groups: int
    players_advance_per_group: Optional[int]
    created_at: dt_date
    player_ids: List[int]  # ✅ Required in response
    knockout_size: int  # ✅ Re-add this

    class Config:
        orm_mode = True

class TournamentMatchResponse(BaseModel):
    id: int
    player1_id: int
    player2_id: int
    player1_name: str
    player2_name: str
    player1_score: Optional[int]
    player2_score: Optional[int]
    winner_id: Optional[int]
    round: str
    stage: str
    set_scores: Optional[List[List[int]]] = []  # ✅ must be here

    class Config:
        from_attributes = True

class GroupMatrixEntry(BaseModel):
    winner: int
    score: str
    set_scores: str

class TournamentDetailsResponse(BaseModel):
    id: int
    name: str
    date: dt_date
    num_players: int
    num_groups: int
    knockout_size: int
    created_at: datetime
    group_matches: List[TournamentMatchResponse]
    knockout_matches: List[TournamentMatchResponse]
    individual_matches: List[TournamentMatchResponse]
    knockout_bracket: dict[str, list[TournamentMatchResponse]] = {}
    final_standings: dict[str, int] = {}
    group_matrix: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class MatchInfo(BaseModel):
    id: int
    player1_id: int
    player2_id: int
    player1_score: int
    player2_score: int
    winner_id: Optional[int]
    round: int
    stage: str

class SetScore(BaseModel):
    set_number: int
    player1_score: int
    player2_score: int

class TournamentMatchResult(BaseModel):
    player1_id: int
    player2_id: int
    player1_score: int  # ✅ Added
    player2_score: int  # ✅ Added
    winner_id: int
    sets: List[SetScore]  # variable number of sets

    class Config:
        from_attributes = True
