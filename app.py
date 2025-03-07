from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Welcome to the Elo Ranking System!"}

# Stores player data with rating and match count
'''{"name": {
    "rating": ...
    "matches": ...
}}
'''
player_ratings: Dict[str, Dict[str, int]] = {}

class MatchResult(BaseModel):
    player1: str
    player2: str
    winner: str

def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    """Calculates new Elo rating based on match outcome."""
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)

@app.post("/submit_match")
def submit_match(result: MatchResult):
    """Updates player ratings based on match results."""

    if result.winner not in [result.player1, result.player2]:
        return {"error": "Winner must be either player1 or player2."}

    if result.player1 == result.player2:
        return {"error": "Players must have different names."}

    # Initialize players if they don't exist
    if result.player1 not in player_ratings:
        player_ratings[result.player1] = {"rating": 1500, "matches": 0}

    if result.player2 not in player_ratings:
        player_ratings[result.player2] = {"rating": 1500, "matches": 0}

    games_played_p1 = player_ratings[result.player1]["matches"]
    games_played_p2 = player_ratings[result.player2]["matches"]

    # Elo Calculation
    if result.winner == result.player1:
        new_rating1 = calculate_elo(player_ratings[result.player1]["rating"], player_ratings[result.player2]["rating"], 1, games_played_p1)
        new_rating2 = calculate_elo(player_ratings[result.player2]["rating"], player_ratings[result.player1]["rating"], 0, games_played_p2)
    else:
        new_rating1 = calculate_elo(player_ratings[result.player1]["rating"], player_ratings[result.player2]["rating"], 0, games_played_p1)
        new_rating2 = calculate_elo(player_ratings[result.player2]["rating"], player_ratings[result.player1]["rating"], 1, games_played_p2)

    # Update player ratings and match count
    player_ratings[result.player1]["rating"] = round(new_rating1)
    player_ratings[result.player2]["rating"] = round(new_rating2)
    player_ratings[result.player1]["matches"] += 1
    player_ratings[result.player2]["matches"] += 1

    return {
        "player1": result.player1,
        "new_rating1": player_ratings[result.player1]["rating"],
        "games_played_p1": player_ratings[result.player1]["matches"],
        "player2": result.player2,
        "new_rating2": player_ratings[result.player2]["rating"],
        "games_played_p2": player_ratings[result.player2]["matches"],
    }

@app.get("/rankings")
def get_rankings():
    """Returns the current Elo rankings sorted by highest rating."""
    sorted_rankings = sorted(player_ratings.items(), key=lambda x: x[1]["rating"], reverse=True)
    return {player: data for player, data in sorted_rankings}
