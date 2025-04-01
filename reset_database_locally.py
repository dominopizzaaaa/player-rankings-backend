import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import engine, Base
from app.models import (
    Player,
    Tournament,
    TournamentPlayer,
    TournamentStanding,
    Match,        # ✅ New unified match table
    SetScore      # ✅ Renamed from TournamentSetScore
)

async def drop_and_recreate_all_tables():
    async with engine.begin() as conn:
        print("⚠️ Dropping all tables...")

        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

        # Drop all existing tables, old names removed
        await conn.execute(text("DROP TABLE IF EXISTS set_scores"))
        await conn.execute(text("DROP TABLE IF EXISTS matches"))
        #await conn.execute(text("DROP TABLE IF EXISTS tournament_players"))
        await conn.execute(text("DROP TABLE IF EXISTS tournament_standings"))
        await conn.execute(text("DROP TABLE IF EXISTS tournaments"))
        #await conn.execute(text("DROP TABLE IF EXISTS players"))

        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        print("✅ All tables dropped.")

        print("🔁 Recreating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables recreated.")

        print("🔢 Resetting AUTO_INCREMENT values...")
        tables = [
            "players", "matches", "set_scores",
            "tournaments", "tournament_players", "tournament_standings"
        ]
        for table in tables:
            await conn.execute(text(f"ALTER TABLE {table} AUTO_INCREMENT = 1"))

        print("✅ AUTO_INCREMENT reset.")

if __name__ == "__main__":
    asyncio.run(drop_and_recreate_all_tables())
