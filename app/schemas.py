from typing import Optional
from pydantic import BaseModel, Field
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

class SetScore(BaseModel):
    set_number: int
    player1_score: int
    player2_score: int

class MatchResult(BaseModel):
    player1_id: int
    player2_id: int
    player1_score: int
    player2_score: int
    winner_id: int
    timestamp: Optional[datetime] = None
    sets: Optional[List[SetScore]] = []
    tournament_id: Optional[int] = None

    class Config:
        from_attributes = True

class MatchResponse(BaseModel):
    id: int
    player1_id: int
    player2_id: Optional[int]
    player1_name: str
    player2_name: Optional[str]
    player1_score: Optional[int]
    player2_score: Optional[int]
    winner_id: Optional[int]
    round: Optional[str]
    stage: Optional[str]
    set_scores: Optional[List[List[int]]]
    timestamp: Optional[datetime] = None  # ✅ new field

    class Config:
        from_attributes = True

class GroupingMode(str, Enum):
    ranked = "ranked"
    random = "random"

class TournamentCreate(BaseModel):
    name: str
    date: dt_date
    num_groups: int
    players_per_group_advancing: int
    player_ids: List[int]  # ✅ New field
    is_customized: Optional[int] = 0

class TournamentResponse(BaseModel):
    id: int
    name: str
    date: dt_date
    num_players: int
    num_groups: int
    players_advance_per_group: Optional[int]
    created_at: dt_date
    player_ids: List[int]
    knockout_size: int
    final_standings: Optional[Dict[str, int]] = None
    is_customized: Optional[int] = 0

    class Config:
        orm_mode = True

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
    group_matches: List[MatchResponse]
    knockout_matches: List[MatchResponse]
    individual_matches: List[MatchResponse]
    knockout_bracket: dict[str, list[MatchResponse]] = Field(default_factory=dict)
    final_standings: dict[str, int] = Field(default_factory=dict)
    group_matrix: Optional[Dict[str, Any]] = None
    is_customized: Optional[int] = 0

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

class MatchHistoryEntry(BaseModel):
    date: datetime
    tournament: bool
    tournament_name: Optional[str] = None
    winner_id: int
    player1_id: int
    player2_id: int
    player1_score: int
    player2_score: int
    set_scores: Optional[List[dict]] = []

class HeadToHeadResponse(BaseModel):
    player1_id: int
    player2_id: int
    matches_played: int
    player1_wins: int
    player2_wins: int
    player1_win_percentage: float
    player2_win_percentage: float
    player1_sets: int
    player2_sets: int
    player1_points: int
    player2_points: int
    most_recent_winner: Optional[int]
    match_history: List[MatchHistoryEntry]

class CustomizedGroup(BaseModel):
    group_number: int
    player_ids: List[int]

class CustomizedKnockoutMatch(BaseModel):
    player1_id: Optional[int]
    player2_id: Optional[int]

class CustomizedTournamentCreate(BaseModel):
    name: str
    date: dt_date
    customized_groups: List[CustomizedGroup]
    customized_knockout: List[CustomizedKnockoutMatch]

# For optional follow-up setup/update
class CustomMatch(BaseModel):
    player1_id: int
    player2_id: Optional[int]
    round: str
    stage: str  # "group" or "knockout"

class CustomTournamentSetup(BaseModel):
    group_assignments: Optional[Dict[int, List[int]]] = None
    custom_matches: List[CustomMatch]
