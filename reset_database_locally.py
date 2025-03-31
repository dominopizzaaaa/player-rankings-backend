import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import engine, Base
from app.models import (
    Tournament,
    TournamentPlayer,
    TournamentMatch,
    TournamentSetScore,
    TournamentStanding  # ✅ Add this import
)

async def drop_and_recreate_tournament_tables():
    async with engine.begin() as conn:
        print("⚠️ Dropping tournament-related tables...")

        # Temporarily disable foreign key checks (MySQL only)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

        # Drop all tournament-related tables
        await conn.execute(text("DROP TABLE IF EXISTS tournament_set_scores"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_matches"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_players"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_standings"))  # ✅ New
        await conn.execute(text("DROP TABLE IF EXISTS tournaments"))

        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        print("✅ Tables dropped.")

        print("🔁 Recreating tables...")
        # Recreate all tournament-related tables
        await conn.run_sync(Base.metadata.create_all, tables=[
            Tournament.__table__,
            TournamentPlayer.__table__,
            TournamentMatch.__table__,
            TournamentSetScore.__table__,
            TournamentStanding.__table__  # ✅ Include this
        ])
        print("✅ Tables recreated.")

        print("🔢 Resetting AUTO_INCREMENT values...")
        await conn.execute(text("ALTER TABLE tournaments AUTO_INCREMENT = 1"))
        await conn.execute(text("ALTER TABLE tournament_players AUTO_INCREMENT = 1"))
        await conn.execute(text("ALTER TABLE tournament_matches AUTO_INCREMENT = 1"))
        await conn.execute(text("ALTER TABLE tournament_set_scores AUTO_INCREMENT = 1"))
        await conn.execute(text("ALTER TABLE tournament_standings AUTO_INCREMENT = 1"))
        print("✅ AUTO_INCREMENT reset.")

if __name__ == "__main__":
    asyncio.run(drop_and_recreate_tournament_tables())
