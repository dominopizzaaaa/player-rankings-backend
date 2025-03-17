from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ✅ Define PlayerBase first
class PlayerBase(BaseModel):
    name: str
    matches_played: int = 0
    rating: int = 1000
    handedness: Optional[str] = None
    forehand_rubber: Optional[str] = None
    backhand_rubber: Optional[str] = None
    blade: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None

# ✅ Now you can inherit PlayerBase
class PlayerCreate(PlayerBase):
    pass

class PlayerResponse(PlayerBase):
    id: int  # ✅ This must be included

    class Config:
        from_attributes = True

# ✅ Match schemas
class MatchCreate(BaseModel):
    player1_id: int
    player2_id: int
    player1_score: int
    player2_score: int
    winner_id: int

class MatchResponse(MatchCreate):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
