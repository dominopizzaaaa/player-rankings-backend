from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from .database import Base

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    matches_played = Column(Integer, default=0)
    rating = Column(Integer, default=1000)
    handedness = Column(String(10), nullable=True)  # Right or Left
    forehand_rubber = Column(String(100), nullable=True)
    backhand_rubber = Column(String(100), nullable=True)
    blade = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player1_score = Column(Integer, nullable=False)
    player2_score = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())  # Auto timestamp