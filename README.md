# Elo Ranking System (Python + FastAPI)

## Project Overview
This project is an Elo ranking system built for XiaobaiQiu, a table tennis club in Singapore. The system is designed to entice players to compete in club tournaments by tracking their rankings dynamically. Elo scores are updated every 10 minutes based on match results, giving players a way to see their progress and stay engaged with the club's competitions.

## Why FastAPI?
After evaluating different backend technologies (Python Flask vs. FastAPI vs. Node.js), we decided to use FastAPI because:
- It's faster than Flask (built-in async support).
- Handles 100 players updating at once efficiently.
- No need for additional dependencies like Celery or Redis.
- Easier to deploy and maintain.

## Tech Stack
- **Backend:** FastAPI (Python 3)
- **Database:** SQLite (or PostgreSQL for production)
- **Task Handling:** FastAPI Background Tasks
- **Hosting:** (TBD – GoDaddy, AWS, or DigitalOcean)