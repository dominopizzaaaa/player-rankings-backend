# Player Rankings Backend

## Overview

The backend of the **Player Rankings** system is built using **FastAPI** and **SQLAlchemy**, providing a high-performance API for handling player data, match records, and Elo ranking calculations.

## Technologies Used

- **FastAPI** – High-performance web framework
- **SQLAlchemy (async)** – ORM for database interactions
- **MySQL (Google Cloud SQL)** – Database for storing players and matches
- **JWT (JSON Web Tokens)** – Secure authentication and admin access control
- **CORS Middleware** – Allows frontend communication with the backend
- **Uvicorn** – ASGI server for FastAPI

## Hosting & Deployment

- The backend is deployed on **Render.com** for automatic builds and hosting.
- Uses **Google Cloud SQL** as the database.
- Runs on **Uvicorn** for high-performance asynchronous execution.

## Features

### 🏆 Player & Match Management
- **CRUD operations** for players and matches.
- **Elo ranking calculation** for each match.
- **Match history tracking** with timestamps.

### 🔒 Authentication & Security
- Uses **JWT-based authentication**.
- Only admins can modify data.
- Authentication is enforced on restricted routes.

### 🔀 API Endpoints

#### **Authentication**
- **POST /token** → Login and retrieve JWT token

#### **Players**
- **GET /players** → Fetch all players
- **GET /players/{id}** → Fetch player by ID
- **POST /players** → Add a new player
- **PATCH /players/{id}** → Update player details
- **DELETE /players/{id}** → Remove player (and all matches)

#### **Matches**
- **GET /matches** → Fetch all matches
- **POST /matches** → Submit a match result (updates Elo ratings)
- **PATCH /matches/{id}** → Update match details
- **DELETE /matches/{id}** → Remove a match

## Database Schema

### **Players Table**
| Column  | Type     | Description |
|---------|---------|-------------|
| id      | INT (PK) | Unique player ID |
| name    | STRING   | Player's name |
| rating  | INT      | Elo rating (default 1500) |
| matches | INT      | Number of matches played |
| handedness | STRING | Left/Right-handed |
| forehand_rubber | STRING | Forehand rubber details |
| backhand_rubber | STRING | Backhand rubber details |
| blade   | STRING   | Blade type |
| age     | INT      | Player's age |
| gender  | STRING   | Male/Female |

### **Matches Table**
| Column  | Type     | Description |
|---------|---------|-------------|
| id      | INT (PK) | Match ID |
| player1_id | INT (FK) | First player ID |
| player2_id | INT (FK) | Second player ID |
| player1_score | INT | Score of Player 1 |
| player2_score | INT | Score of Player 2 |
| winner_id | INT (FK) | Winner's ID |
| timestamp | DATETIME | Match time |

## Elo Rating Calculation

The Elo rating is calculated using:

```python
def calculate_elo(old_rating, opponent_rating, outcome, games_played):
    if games_played <= 10:
        K = 40
    elif games_played <= 200:
        K = 24
    else:
        K = 16
    expected_score = 1 / (1 + 10 ** ((opponent_rating - old_rating) / 400))
    return old_rating + K * (outcome - expected_score)
```
- **K-factor** varies based on the number of games played.
- **Expected score** determines the probability of winning.
- **Outcome (1 = win, 0 = loss)** updates the rating accordingly.

## Deployment Steps

1. Clone the repository:
   ```sh
   git clone https://github.com/your-repo/player-rankings-backend.git
   ```

2. Install dependencies:
   ```sh
   cd player-rankings-backend
   pip install -r requirements.txt
   ```

3. Create `.env` file:
   ```sh
   DATABASE_URL="mysql+asyncmy://elo_user:password@your-database-url/player_rankings"
   SECRET_KEY="your_secret_key"
   ```

4. Run migrations:
   ```sh
   alembic upgrade head
   ```

5. Start the FastAPI server:
   ```sh
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

6. Deploy to **Render.com**

This backend ensures **secure, fast, and scalable** Elo ranking management. 🚀