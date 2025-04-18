from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime, timezone
from typing import Optional, Dict

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
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=True)  # NULL for normal matches
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    player1_score = Column(Integer, nullable=True)
    player2_score = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    round = Column(String(50), nullable=True)  # e.g., "Group A", "Quarterfinal", etc.
    stage = Column(String(20), nullable=True)  # "group", "knockout", or None
    set_scores = relationship("SetScore", back_populates="match", cascade="all, delete-orphan")
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    match_winner = relationship("Player", foreign_keys=[winner_id])

    tournament = relationship("Tournament", back_populates="matches", lazy="joined")

class Tournament(Base):
    __tablename__ = "tournaments"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    knockout_size = Column(Integer)  # ✅ Re-add this
    num_players = Column(Integer, nullable=False)
    num_groups = Column(Integer, nullable=False)
    players_advance_per_group = Column(Integer, nullable=True)
    created_at = Column(Date, nullable=False)
    standings = relationship("TournamentStanding", back_populates="tournament", cascade="all, delete-orphan")
    players = relationship("TournamentPlayer", back_populates="tournament", cascade="all, delete-orphan")
    is_customized = Column(Integer, default=0)  # 1 = customized, 0 = auto
    final_standings: Optional[Dict[str, int]] = None

    matches = relationship("Match", back_populates="tournament", cascade="all, delete-orphan")

class TournamentStanding(Base):
    __tablename__ = "tournament_standings"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    position = Column(Integer, nullable=False)  # 1 = 1st, 2 = 2nd, etc.

    tournament = relationship("Tournament", back_populates="standings")
    player = relationship("Player")

class TournamentPlayer(Base):
    __tablename__ = "tournament_players"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    group_number = Column(Integer, nullable=False)
    seed = Column(Integer, nullable=True)  # based on Elo
    tournament = relationship("Tournament", back_populates="players")

class SetScore(Base):
    __tablename__ = "set_scores"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    set_number = Column(Integer)
    player1_score = Column(Integer)
    player2_score = Column(Integer)

    match = relationship("Match", back_populates="set_scores")
