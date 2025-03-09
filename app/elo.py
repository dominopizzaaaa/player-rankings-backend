import math

K = 32  # Elo K-factor, can be adjusted

def calculate_elo(winner_elo, loser_elo):
    expected_winner = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
    expected_loser = 1 - expected_winner

    new_winner_elo = winner_elo + K * (1 - expected_winner)
    new_loser_elo = loser_elo + K * (0 - expected_loser)

    return round(new_winner_elo), round(new_loser_elo)
