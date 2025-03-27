from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Boolean, Enum
from sqlalchemy.sql import func
from .database import Base
import enum

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    matches = Column(Integer, default=0)
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
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=False)  # ✅ Add winner
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class GroupingMode(enum.Enum):
    RANKED = "ranked"
    RANDOM = "random"

class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    num_players = Column(Integer, nullable=False)
    num_groups = Column(Integer, nullable=False)
    knockout_size = Column(Integer, nullable=False)
    grouping_mode = Column(Enum(GroupingMode), nullable=False)
    created_by = Column(String, nullable=False)  # or Integer if linking to a user table
    created_at = Column(Date, nullable=False)


class TournamentPlayer(Base):
    __tablename__ = "tournament_players"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    group_number = Column(Integer, nullable=False)
    seed = Column(Integer, nullable=True)  # based on Elo


class TournamentMatch(Base):
    __tablename__ = "tournament_matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    stage = Column(String, nullable=False)  # e.g., "RR", "KO"
    group_number = Column(Integer, nullable=True)
    round_number = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    updated = Column(Boolean, default=False)