from pydantic import BaseModel

class PlayerCreate(BaseModel):
    name: str

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
