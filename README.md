# Elo Ranking System (Python + FastAPI)

## Project Overview
This project is an Elo ranking system built for **XiaobaiQiu**, a table tennis club in Singapore.  
The system is designed to **entice players to compete in club tournaments** by tracking their rankings dynamically.  
Elo scores are updated **every 10 minutes** based on match results, giving players a way to see their progress and stay engaged with the club's competitions.

## Why FastAPI?
After evaluating different backend technologies (**Flask vs. FastAPI vs. Node.js**), we decided to use **FastAPI** because:
- It's **faster** than Flask (**built-in async support**).
- Handles **100 players updating at once efficiently**.
- No need for additional dependencies like Celery or Redis.
- **Easier to deploy and maintain**.

## Tech Stack
- **Backend:** FastAPI (Python 3)
- **Database:** **PostgreSQL** (via SQLAlchemy ORM)
- **Task Handling:** FastAPI Background Tasks
- **Hosting:** *(TBD – GoDaddy, AWS, or DigitalOcean)*

---

# 📌 **Database Setup (PostgreSQL + SQLAlchemy)**
This section documents the **database setup**, including technologies used, why they were chosen, and how they were implemented.

## 🛠 **Technologies Used**
| **Technology**  | **Why It Was Used?** |
|---------------|----------------|
| **PostgreSQL** | A relational database used to store **player rankings persistently**. Unlike in-memory dictionaries, PostgreSQL ensures that rankings **are saved even if the server restarts**. |
| **SQLAlchemy ORM** | Simplifies interaction with PostgreSQL by allowing **database queries using Python classes and objects** instead of raw SQL. This increases **security and maintainability**. |
| **Alembic Migrations** | Tracks **database schema changes** (e.g., creating tables) and applies them automatically. |

---

## 📌 **Setting Up PostgreSQL**
### **1️⃣ Install PostgreSQL**
```bash
brew install postgresql
brew services start postgresql
```
### **2️⃣ Log into PostgreSQL**
```bash
psql -U postgres
```
### **3️⃣ Create the `elo_ranking` Database**
```sql
CREATE DATABASE elo_ranking OWNER postgres;
```
### **4️⃣ Verify Database Creation**
```sql
\l  -- Lists all databases
```

---

## 📌 **Connecting FastAPI to PostgreSQL**
### **🔹 Install Required Python Libraries**
```bash
pip install sqlalchemy psycopg2 alembic
```
- **SQLAlchemy** → ORM for managing the database.
- **psycopg2** → PostgreSQL database driver.
- **Alembic** → Handles schema migrations.

---

## 📌 **Database Connection Setup (`database.py`)**
Created a **database connection** using **SQLAlchemy**:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:dominopizza@localhost/elo_ranking"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
---

## 📌 **Creating the Players Table (`models.py`)**
Created the `players` table:
```python
from sqlalchemy import Column, Integer, String
from database import Base

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    rating = Column(Integer, default=1500)
    matches = Column(Integer, default=0)
```
---

## 📌 **Applying Database Migrations with Alembic**
Since PostgreSQL doesn’t **automatically detect Python models**, we used **Alembic** for schema migrations.

### **1️⃣ Initialize Alembic**
```bash
alembic init alembic
```
### **2️⃣ Configure Alembic to use PostgreSQL in `alembic.ini`**
```ini
sqlalchemy.url = postgresql://postgres:dominopizza@localhost/elo_ranking
```
### **3️⃣ Generate a Migration File**
```bash
alembic revision --autogenerate -m "Create players table"
```
### **4️⃣ Apply the Migration**
```bash
alembic upgrade head
```

---

## 📌 **Updating FastAPI Endpoints to Use PostgreSQL**
### **Before (In-Memory Dictionary)**
```python
player_ratings = {}
```
### **After (Using PostgreSQL)**
Modified `/submit_match` endpoint:
```python
from sqlalchemy.orm import Session
from database import get_db
from models import Player

@app.post("/submit_match")
def submit_match(result: MatchResult, db: Session = Depends(get_db)):
    player1 = db.query(Player).filter(Player.name == result.player1).first()
    player2 = db.query(Player).filter(Player.name == result.player2).first()

    if not player1:
        player1 = Player(name=result.player1)
        db.add(player1)
    
    if not player2:
        player2 = Player(name=result.player2)
        db.add(player2)

    db.commit()

    return {"message": "Match recorded successfully"}
```
---

## 📌 **Summary of Database Setup**
| **Step** | **What We Did** | **Why?** |
|----------|----------------|----------|
| **1️⃣ Installed PostgreSQL** | Set up a persistent database | Store rankings permanently |
| **2️⃣ Connected FastAPI** | Used SQLAlchemy ORM | Easier, secure database management |
| **3️⃣ Created `players` Table** | Defined `models.py` | Structure to store player Elo ratings |
| **4️⃣ Set Up Alembic** | Managed database migrations | Track schema changes automatically |
| **5️⃣ Updated API** | Used PostgreSQL for `/submit_match` & `/rankings` | Store & retrieve Elo data |
| **6️⃣ Tested API** | Sent match results & checked rankings | Verified database integration |

---

## 🚀 **Next Steps**
Now that the **database is fully integrated**, we can:
1. **Deploy the API Online** (so others can access it).
2. **Build a Frontend Leaderboard** (display rankings on a website).
3. **Optimize Queries** (for better performance).
