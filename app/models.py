from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Boolean, Enum
from sqlalchemy.sql import relationship
from .database import Base
import enum
from datetime import datetime, timezone

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # ✅ Explicit length added
    matches = Column(Integer, default=0)
    rating = Column(Integer, default=1500)
    handedness = Column(String(10), nullable=True)  # ✅ Explicit length added
    forehand_rubber = Column(String(100), nullable=True)  # ✅ Explicit length added
    backhand_rubber = Column(String(100), nullable=True)  # ✅ Explicit length added
    blade = Column(String(100), nullable=True)  # ✅ Explicit length added
    age = Column(Integer, nullable=True)
    gender = Column(String(10), nullable=True)  # ✅ Explicit length added

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player1_score = Column(Integer, nullable=False, default=0)
    player2_score = Column(Integer, nullable=False, default=0)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    match_winner = relationship("Player", foreign_keys=[winner_id])

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