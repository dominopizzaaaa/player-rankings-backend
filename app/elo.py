# Elo calculation function
def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16

    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)
