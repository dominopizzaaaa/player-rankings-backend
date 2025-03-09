from sqlalchemy import Column, Integer, String
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
