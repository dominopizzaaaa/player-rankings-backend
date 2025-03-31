
# Player Rankings Backend

This is the backend service for the Elo-based Player Rankings System, built with FastAPI and connected to a MySQL database using SQLAlchemy.

## Features

- ✅ Player Management (Add, Edit, Delete players)
- ✅ Match Management (Add matches, calculate Elo updates)
- ✅ Tournament System (Round-robin group stage + knockout bracket)
- ✅ Tournament Bracket Generator with full match dependency tracking
- ✅ Group stage ranking logic with tiebreakers
- ✅ Elo updates on tournament matches
- ✅ Final standings and 3rd place match handling
- ✅ Undo/reset tournaments (matches deleted, Elo unaffected)

---

## 🧠 Tournament System Overview

### 1. Tournament Creation

When creating a tournament via the API:
- Admin selects a list of registered player IDs
- Chooses number of groups (`num_groups`)
- Chooses how many top players from each group will advance (`players_per_group_advancing`)
- The system calculates total advancing players and rounds up to the next power of 2 for the knockout size

Example:
- 3 groups, top 2 advance → 6 players
- Knockout size = 8 → 2 byes added for highest-ranked players

---

### 2. Group Stage

- Players are divided into `num_groups` as evenly as possible
- Each group is a round-robin: all players play each other once
- Match results are submitted manually via the API or frontend

#### Group Rankings Logic (Tiebreakers in order):
1. Number of Wins
2. Head-to-head result (if tied between two)
3. Set difference (sets won - sets lost)
4. Point difference (total points scored - points conceded)

Group stage standings are updated dynamically as matches are submitted.

---

### 3. Knockout Stage

Once all group stage matches are submitted:
- Top `players_per_group_advancing` from each group are selected
- Bracket is filled with:
  - First: group winners
  - Then: best-ranked 2nd place players (if needed)
- Players from the same group are avoided in Round 1 unless unavoidable
- Byes are assigned to highest-ranked players if knockout size is larger than participants

#### Bracket Generation:
- All knockout matches are pre-generated with `p1_source_match_id` and `p2_source_match_id` dependencies
- Each match advances winners by resolving these dependencies
- A 3rd/4th place match is added automatically if there are at least 4 players

---

### 4. Final Standings

Once final and 3rd place matches are completed:
- Final standings are stored: 1st to 4th place
- Displayed in frontend

---

### 5. Elo Rating Updates

- Every submitted match (including tournament matches) updates Elo ratings for both players
- Elo is updated using a basic Elo formula

---

## API Endpoints

- `POST /players` — Add player
- `POST /matches` — Submit match
- `POST /tournaments` — Create tournament
- `POST /tournaments/{tournament_id}/submit_result` — Submit tournament match result
- `GET /tournaments/{id}` — Get tournament details
- `POST /tournaments/{id}/undo` — Reset tournament (delete matches only)